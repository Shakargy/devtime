"""Bundled demo repository support for `dtc demo init`.

This lets people who installed DevTime from PyPI (`pipx install devtime-ei`) try it
without cloning the source repository. It copies a small, static example repo that
ships inside the installed package into the current working directory.

It only copies static files. It never executes code, never installs anything, never
runs tests or migrations, and never touches the network. Nothing leaves the machine.
"""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

# Directory name created in the current working directory.
DEMO_DIR_NAME = "devtime-demo-saas"

# The packaged demo lives at src/devtime/resources/demo-saas/ and ships in the wheel
# via [tool.setuptools.package-data].
_RESOURCE_SUBPATH = ("resources", "demo-saas")

# Artifacts that must never end up in a copied demo, stripped defensively after copy.
_FORBIDDEN_DIRS = {".devtime", ".git", "node_modules", "__pycache__", ".cache"}
_FORBIDDEN_FILE_SUFFIXES = (".sqlite", ".sqlite3", ".db")


class DemoExistsError(Exception):
    """Raised when the demo directory already exists and force was not requested."""

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(str(path))


def packaged_demo_source() -> Path:
    """Return a filesystem path to the demo directory bundled in the package."""
    root = resources.files("devtime")
    source = root.joinpath(*_RESOURCE_SUBPATH)
    # In a normal wheel/editable install this is already a real path on disk.
    return Path(str(source))


def _strip_forbidden(dest: Path) -> None:
    """Remove any artifacts that must never be part of a shared demo."""
    for path in sorted(dest.rglob("*"), reverse=True):
        if path.is_dir() and path.name in _FORBIDDEN_DIRS:
            shutil.rmtree(path, ignore_errors=True)
        elif path.is_file() and path.suffix.lower() in _FORBIDDEN_FILE_SUFFIXES:
            path.unlink(missing_ok=True)


def create_demo(dest_parent: Path, *, force: bool = False) -> Path:
    """Copy the bundled demo into ``dest_parent/devtime-demo-saas``.

    Writes only inside ``dest_parent``. Returns the created directory path.
    Raises :class:`DemoExistsError` if the destination exists and ``force`` is False.
    """
    dest = dest_parent / DEMO_DIR_NAME
    if dest.exists():
        if not force:
            raise DemoExistsError(dest)
        shutil.rmtree(dest)

    source = packaged_demo_source()
    if not source.is_dir():
        raise FileNotFoundError(f"Bundled demo not found at {source}")

    # as_file guarantees a real filesystem path even if the package were zipped.
    with resources.as_file(resources.files("devtime").joinpath(*_RESOURCE_SUBPATH)) as src_path:
        shutil.copytree(src_path, dest)

    _strip_forbidden(dest)
    return dest
