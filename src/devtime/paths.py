"""Local path helpers (Builder Edition, Chapter 5)."""

from pathlib import Path

DEV_DIR = ".devtime"
DB_NAME = "devtime.sqlite"
CONFIG_NAME = "config.yaml"
IGNORE_NAME = ".devtimeignore"


def repo_root() -> Path:
    return Path.cwd()


def devtime_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / DEV_DIR


def db_path(root: Path | None = None) -> Path:
    return devtime_dir(root) / DB_NAME


def config_path(root: Path | None = None) -> Path:
    return devtime_dir(root) / CONFIG_NAME


def ignore_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / IGNORE_NAME


def backups_dir(root: Path | None = None) -> Path:
    return devtime_dir(root) / "backups"


def logs_dir(root: Path | None = None) -> Path:
    return devtime_dir(root) / "logs"


def is_initialized(root: Path | None = None) -> bool:
    return db_path(root).exists()
