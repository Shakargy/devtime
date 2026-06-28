"""Tests for `dtc demo init` (v0.1.1 pipx onboarding).

The demo command copies a static example repo bundled in the package so PyPI
installs can try DevTime without cloning. These tests cover the copy, the
no-overwrite guard, --force, artifact hygiene, and that the copied demo scans.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devtime.cli import app
from devtime.demo import DEMO_DIR_NAME, DemoExistsError, create_demo
from devtime.fixtures.runner import run_devtime_scan

runner = CliRunner()


def test_create_demo_creates_directory(tmp_path):
    dest = create_demo(tmp_path)
    assert dest == tmp_path / DEMO_DIR_NAME
    assert dest.is_dir()


def test_created_demo_contains_expected_files(tmp_path):
    dest = create_demo(tmp_path)
    # Marker file plus billing-webhook and auth evidence files.
    assert (dest / "package.json").is_file()
    assert (dest / "src" / "billing" / "stripe-webhook.ts").is_file()
    assert (dest / "src" / "auth" / "login.ts").is_file()
    assert (dest / "tests" / "stripe-signature.test.ts").is_file()


def test_created_demo_has_no_devtime_or_sqlite(tmp_path):
    dest = create_demo(tmp_path)
    assert not (dest / ".devtime").exists()
    assert list(dest.rglob("*.sqlite")) == []
    assert list(dest.rglob("*.db")) == []
    assert list(dest.rglob("node_modules")) == []


def test_second_create_without_force_raises(tmp_path):
    create_demo(tmp_path)
    with pytest.raises(DemoExistsError):
        create_demo(tmp_path)


def test_force_replaces_existing(tmp_path):
    dest = create_demo(tmp_path)
    # Leave a stray marker; --force should remove the whole directory first.
    stray = dest / "STRAY_MARKER.txt"
    stray.write_text("remove me")
    create_demo(tmp_path, force=True)
    assert not stray.exists()
    assert (dest / "package.json").is_file()


def test_copied_demo_scans_core_concepts(tmp_path):
    dest = create_demo(tmp_path)
    intelligence = run_devtime_scan(dest)
    names = {ci.concept.name for ci in intelligence}
    assert "Authentication" in names
    assert "Billing Webhooks" in names


# --- CLI surface ------------------------------------------------------------

def test_cli_demo_init_succeeds(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["demo", "init"])
    assert result.exit_code == 0
    assert (tmp_path / DEMO_DIR_NAME / "package.json").is_file()
    assert "devtime-demo-saas" in result.stdout


def test_cli_demo_init_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["demo", "init"]).exit_code == 0
    result = runner.invoke(app, ["demo", "init"])
    assert result.exit_code != 0
    assert "already exists" in result.stdout
    assert "--force" in result.stdout


def test_cli_demo_init_force(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["demo", "init"]).exit_code == 0
    result = runner.invoke(app, ["demo", "init", "--force"])
    assert result.exit_code == 0
