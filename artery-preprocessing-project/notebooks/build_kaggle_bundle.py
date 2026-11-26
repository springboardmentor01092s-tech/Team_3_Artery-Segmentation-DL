"""Build a Kaggle-safe project-code bundle without secrets, DB, or source images."""
from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INCLUDED = (
    PROJECT_ROOT / "backend" / "app",
    PROJECT_ROOT / "backend" / "requirements-ml.txt",
    PROJECT_ROOT / "backend" / "checkpoints" / "best_stenosis_unet_optimized.pth",
    PROJECT_ROOT / "backend" / "checkpoints" / "best_stenosis_unet_optimized.pth.threshold.json",
)
DESTINATION = PROJECT_ROOT / "kaggle_project_code.zip"


def main() -> None:
    missing = [path for path in INCLUDED if not path.exists()]
    if missing:
        raise FileNotFoundError("Required Kaggle bundle inputs are missing: " + ", ".join(map(str, missing)))
    with ZipFile(DESTINATION, "w", compression=ZIP_DEFLATED) as archive:
        for item in INCLUDED:
            paths = item.rglob("*") if item.is_dir() else (item,)
            for path in paths:
                if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                    continue
                archive.write(path, path.relative_to(PROJECT_ROOT).as_posix())
    print(f"Created {DESTINATION} ({DESTINATION.stat().st_size / 2**20:.1f} MiB)")
    print("Included backend source, optional ML requirements, active baseline checkpoint, and threshold sidecar.")
    print("Excluded .env, database, uploads, processed files, and the ARCADE dataset.")


if __name__ == "__main__":
    main()
