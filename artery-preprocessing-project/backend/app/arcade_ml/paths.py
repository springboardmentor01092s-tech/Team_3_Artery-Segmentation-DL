import os
from pathlib import Path


def complete_project_root() -> Path:
    override = os.environ.get("COMPLETE_PROJECT_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3]


def arcade_root() -> Path:
    """Original ARCADE folder (read-only). Override with ARCADE_ROOT for Kaggle."""
    from app.core.config import get_settings

    return get_settings().resolved_arcade_root()


def stenosis_split_dir(split: str) -> Path:
    return arcade_root() / "stenosis" / split


def syntax_split_dir(split: str) -> Path:
    return arcade_root() / "syntax" / split


def derived_dir() -> Path:
    return complete_project_root() / "dataset" / "derived"


def reports_dir() -> Path:
    return complete_project_root() / "reports"


def checkpoints_dir() -> Path:
    return complete_project_root() / "backend" / "checkpoints"
