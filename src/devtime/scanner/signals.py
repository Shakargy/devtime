"""Scan orchestration (Builder Edition, Chapter 7 pipeline).

scan repository -> load config -> load ignore rules -> walk files safely ->
classify -> hash -> extract signals -> persist files and signals -> detect
concepts -> build evidence -> generate claims -> compute scores -> write summary.

Never executes repository code, never makes network calls.
"""

from __future__ import annotations

import hashlib
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from devtime import __version__, config, paths
from devtime.db import connection, migrations, repository
from devtime.intelligence import claims as claims_mod
from devtime.intelligence import concepts as concepts_mod
from devtime.intelligence import evidence as evidence_mod
from devtime.scanner import ignore as ignore_mod
from devtime.scanner.extractors import (
    config_files,
    docs,
    nextjs,
    python,
    tests,
    typescript,
)
from devtime.scanner.extractors.base import Signal
from devtime.scanner.file_walker import WalkedFile, walk_repository
from devtime.scanner.language import classify_language


SUPPORTED_CONCEPT_FAMILIES = (
    "Authentication", "Billing Webhooks", "Background Jobs",
    "Data Export", "Admin Permissions", "File Uploads",
)

# Frameworks whose routes/controllers V0 does not parse, keyed by a dependency token.
UNSUPPORTED_FRAMEWORKS = {
    "django": "Django routes are not parsed in V0; route coverage may be incomplete.",
    "@nestjs/core": "NestJS controller parsing is not supported in V0; backend route coverage may be incomplete.",
    "@nestjs/common": "NestJS controller parsing is not supported in V0; backend route coverage may be incomplete.",
    "rails": "Rails routes are not parsed in V0; route coverage may be incomplete.",
    "laravel/framework": "Laravel routes are not parsed in V0; route coverage may be incomplete.",
}


@dataclass
class ScanResult:
    file_count: int
    signal_count: int
    concept_count: int
    intelligence: list[claims_mod.ConceptIntelligence]
    duration_seconds: float = 0.0
    pruned_dirs: int = 0
    skipped_files: int = 0
    framework_warnings: list[str] = field(default_factory=list)


def detect_framework_warnings(signals: list[Signal]) -> list[str]:
    """Surface coverage gaps for frameworks V0 cannot parse (Trust Repair v0.0.6)."""
    deps = {
        (s.name or "").lower()
        for s in signals
        if s.kind == "dependency" and s.name
    }
    warnings: list[str] = []
    seen: set[str] = set()
    for token, message in UNSUPPORTED_FRAMEWORKS.items():
        if token in deps and message not in seen:
            warnings.append(f"Framework coverage warning: {message}")
            seen.add(message)
    return warnings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def _is_migration_path(rel_path: str) -> bool:
    """DB migrations describe schema history, not live behavior or workers.

    Reality Validation finding: an Alembic migration named *_add_jobs.py was being
    used as Background Jobs evidence. Migration files must not produce
    concept-defining signals.
    """
    low = rel_path.lower()
    return (
        "/migrations/" in low
        or low.startswith("migrations/")
        or "/alembic/versions/" in low
        or "alembic/versions/" in low
    )


def _extract(file: WalkedFile, language: str | None) -> list[Signal]:
    # Migrations are scanned/hashed but never become concept evidence.
    if _is_migration_path(file.rel_path):
        return []

    out: list[Signal] = []
    if file.is_test:
        out += tests.extract_test_signals(file)
    if file.is_doc or language == "markdown":
        out += docs.extract_doc_signals(file)
    if language == "typescript":
        out += typescript.extract_typescript_signals(file)
        out += nextjs.extract_nextjs_signals(file)
    elif language == "python":
        out += python.extract_python_signals(file)
    # Config/manifest extraction by filename, regardless of language.
    out += config_files.extract_config_signals(file)
    return out


def run_scan(
    root: Path | None = None, *, refresh: bool = False, progress: bool = False
) -> ScanResult:
    import sys
    import time

    started = time.perf_counter()
    root = root or paths.repo_root()
    if not paths.is_initialized(root):
        migrations.init_repo(root)

    cfg = config.load_config(root)
    scanner_cfg = cfg["scanner"]
    max_bytes = int(scanner_cfg["max_file_size_kb"]) * 1024

    matcher = ignore_mod.build_matcher(
        root,
        respect_gitignore=bool(scanner_cfg["respect_gitignore"]),
        respect_devtimeignore=bool(scanner_cfg["respect_devtimeignore"]),
    )

    conn = connection.connect(root)
    try:
        repo_id = repository.add_repository_if_missing(conn, root)
        scan_id = f"scan-{uuid.uuid4().hex[:10]}"
        conn.execute(
            "INSERT INTO scans(id, repository_id, started_at, status, devtime_version) "
            "VALUES (?,?,?,?,?)",
            (scan_id, repo_id, _now(), "running", __version__),
        )
        conn.commit()

        all_signals: list[Signal] = []
        file_count = 0
        walk_stats: dict = {"pruned_dirs": 0, "skipped_files": 0}

        if progress:
            print("Scanning locally. No code execution. No network.", file=sys.stderr)

        for wf in walk_repository(
            root, matcher, max_bytes,
            follow_symlinks=bool(scanner_cfg["follow_symlinks"]),
            stats=walk_stats,
        ):
            if progress and file_count and file_count % 1000 == 0:
                print(f"Progress: {file_count} files scanned...", file=sys.stderr)
            language = classify_language(wf.rel_path)
            file_id = f"file-{uuid.uuid4().hex[:10]}"
            conn.execute(
                "INSERT OR REPLACE INTO files"
                "(id, repository_id, path, extension, language, sha256, size_bytes, "
                " is_test, is_doc, ignored, last_seen_scan_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    file_id,
                    repo_id,
                    wf.rel_path,
                    wf.extension,
                    language,
                    _hash_file(wf.path),
                    wf.size_bytes,
                    1 if wf.is_test else 0,
                    1 if wf.is_doc else 0,
                    0,
                    scan_id,
                ),
            )
            file_count += 1

            for s in _extract(wf, language):
                all_signals.append(s)
                conn.execute(
                    "INSERT INTO signals"
                    "(id, scan_id, file_id, kind, name, value, start_line, end_line, "
                    " confidence, metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        f"sig-{uuid.uuid4().hex[:10]}",
                        scan_id,
                        file_id,
                        s.kind,
                        s.name,
                        s.value,
                        s.start_line,
                        s.end_line,
                        s.confidence,
                        "{}",
                    ),
                )
        conn.commit()

        # Detect concepts -> build evidence -> generate claims + uncertainty.
        candidates = concepts_mod.detect_concepts(all_signals)
        intelligence: list[claims_mod.ConceptIntelligence] = []
        for cand in candidates:
            ev = evidence_mod.build_evidence(cand)
            ci = claims_mod.build_concept_intelligence(cand, ev)
            intelligence.append(ci)

        # Persist derived memory (replace machine-derived rows; keep human decisions).
        repository.clear_derived_memory(conn)
        repository.save_intelligence(conn, repo_id, intelligence)

        conn.execute(
            "UPDATE scans SET finished_at=?, status=?, file_count=?, signal_count=? "
            "WHERE id=?",
            (_now(), "completed", file_count, len(all_signals), scan_id),
        )
        conn.commit()

        return ScanResult(
            file_count=file_count,
            signal_count=len(all_signals),
            concept_count=len(intelligence),
            intelligence=intelligence,
            duration_seconds=round(time.perf_counter() - started, 2),
            pruned_dirs=walk_stats.get("pruned_dirs", 0),
            skipped_files=walk_stats.get("skipped_files", 0),
            framework_warnings=detect_framework_warnings(all_signals),
        )
    finally:
        conn.close()
