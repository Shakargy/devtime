"""Unit tests for claim transitions between two snapshots (v0.7.0).

compute_transitions is pure, so every classification rule is tested here
directly, without git or a scan.
"""

from devtime.intelligence import review as rv
from devtime.intelligence import verification as ver


def _r(slug, status, why="summary", deps=(), missing=()):
    return ver.VerificationResult(
        claim_slug=slug,
        claim_name=slug.title(),
        statement="statement",
        status=status,
        why=[why],
        supporting=[],
        contradictions=[],
        missing=list(missing),
        limitations=[],
        scan_id="scan",
        verified_at="t",
        engine_version="0",
        dependencies=list(deps),
    )


def _kind(base_status, head_status, changed=frozenset(), deps=(), base_why="s", head_why="s"):
    base = [_r("c", base_status, base_why, deps)]
    head = [_r("c", head_status, head_why, deps)]
    return rv.compute_transitions(base, head, set(changed))[0].kind


# --- status changes -------------------------------------------------------------

def test_supported_to_weak_is_a_regression():
    assert _kind(ver.SUPPORTED, ver.WEAK) == rv.REGRESSION


def test_any_move_into_contradicted_is_a_regression():
    assert _kind(ver.WEAK, ver.CONTRADICTED) == rv.REGRESSION
    assert _kind(ver.SUPPORTED, ver.CONTRADICTED) == rv.REGRESSION


def test_gaining_support_is_an_improvement():
    assert _kind(ver.WEAK, ver.SUPPORTED) == rv.IMPROVEMENT
    assert _kind(ver.CONTRADICTED, ver.WEAK) == rv.IMPROVEMENT


def test_new_surface_is_newly_applicable_not_an_improvement():
    # A claim that starts to apply is not "better" or "worse"; it is new.
    assert _kind(ver.NOT_APPLICABLE, ver.WEAK) == rv.NEWLY_APPLICABLE
    assert _kind(ver.NOT_APPLICABLE, ver.SUPPORTED) == rv.NEWLY_APPLICABLE


def test_lost_surface_is_no_longer_applicable_not_a_regression():
    # A removed surface is not a loss of evidence; it may have been deleted,
    # renamed, or moved outside scanner coverage.
    assert _kind(ver.SUPPORTED, ver.NOT_APPLICABLE) == rv.NO_LONGER_APPLICABLE


def test_weak_to_unknown_does_not_invent_a_direction():
    assert _kind(ver.WEAK, ver.UNKNOWN) == rv.EVIDENCE_CHANGED


# --- same status ----------------------------------------------------------------

def test_same_status_with_touched_dependency_is_evidence_changed():
    kind = _kind(ver.SUPPORTED, ver.SUPPORTED, changed={"src/a.ts"}, deps=["src/a.ts"])
    assert kind == rv.EVIDENCE_CHANGED


def test_same_status_with_different_summary_is_evidence_changed():
    kind = _kind(ver.WEAK, ver.WEAK, base_why="1 of 2", head_why="1 of 4")
    assert kind == rv.EVIDENCE_CHANGED


def test_untouched_claim_is_unchanged_and_not_reported():
    ts = rv.compute_transitions(
        [_r("c", ver.SUPPORTED, deps=["src/a.ts"])],
        [_r("c", ver.SUPPORTED, deps=["src/a.ts"])],
        {"README.md"},
    )
    assert ts[0].kind == rv.UNCHANGED
    assert rv.reportable(ts) == []


def test_not_applicable_at_both_commits_is_never_evidence_changed():
    ts = rv.compute_transitions(
        [_r("c", ver.NOT_APPLICABLE, why="none")],
        [_r("c", ver.NOT_APPLICABLE, why="none here either")],
        {"src/anything.ts"},
    )
    assert ts[0].kind == rv.UNCHANGED


# --- evidence attribution -------------------------------------------------------

def test_changed_evidence_lists_only_dependencies_that_changed():
    ts = rv.compute_transitions(
        [_r("c", ver.SUPPORTED, deps=["src/a.ts", "src/b.ts"])],
        [_r("c", ver.WEAK, deps=["src/a.ts", "src/b.ts"])],
        {"src/a.ts", "README.md"},
    )
    assert ts[0].changed_evidence == ["src/a.ts"]


def test_renamed_dependency_is_recognized_through_its_old_path():
    # The caller passes both paths of a rename; a claim that depended on the old
    # path is affected even though that path no longer exists.
    ts = rv.compute_transitions(
        [_r("c", ver.SUPPORTED, deps=["src/old.ts"])],
        [_r("c", ver.SUPPORTED, deps=["src/new.ts"])],
        {"src/old.ts", "src/new.ts"},
    )
    assert ts[0].kind == rv.EVIDENCE_CHANGED
    assert ts[0].changed_evidence == ["src/new.ts", "src/old.ts"]


def test_claim_missing_from_one_side_is_treated_as_not_applicable():
    ts = rv.compute_transitions([], [_r("c", ver.WEAK)], set())
    assert ts[0].kind == rv.NEWLY_APPLICABLE
    assert ts[0].base_status == ver.NOT_APPLICABLE


# --- ordering and determinism ---------------------------------------------------

def test_regressions_are_reported_first():
    base = [_r("a", ver.WEAK), _r("b", ver.SUPPORTED), _r("z", ver.NOT_APPLICABLE)]
    head = [_r("a", ver.SUPPORTED), _r("b", ver.WEAK), _r("z", ver.WEAK)]
    kinds = [t.kind for t in rv.compute_transitions(base, head, set())]
    assert kinds == [rv.REGRESSION, rv.NEWLY_APPLICABLE, rv.IMPROVEMENT]


def test_transitions_are_deterministic():
    base = [_r("b", ver.SUPPORTED, deps=["x"]), _r("a", ver.WEAK)]
    head = [_r("a", ver.SUPPORTED), _r("b", ver.WEAK, deps=["x"])]
    first = [t.to_dict() for t in rv.compute_transitions(base, head, {"x"})]
    second = [t.to_dict() for t in rv.compute_transitions(list(reversed(base)), head, {"x"})]
    assert first == second


def test_summary_counts_every_claim():
    base = [_r("a", ver.SUPPORTED), _r("b", ver.WEAK), _r("c", ver.WEAK)]
    head = [_r("a", ver.WEAK), _r("b", ver.WEAK), _r("c", ver.SUPPORTED)]
    counts = rv.summarize(rv.compute_transitions(base, head, set()))
    assert counts[rv.REGRESSION] == 1
    assert counts[rv.IMPROVEMENT] == 1
    assert counts[rv.UNCHANGED] == 1
    assert sum(counts.values()) == 3
