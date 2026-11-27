
from pathlib import Path
import zipfile

# Your project folder
PROJECT_DIR = Path(r"C:\Users\namde\artery-stenosis-project")

# ZIP will be created on Desktop
ZIP_PATH = Path.home() / "Desktop" / "artery-stenosis-project.zip"

# Folders to include
INCLUDE_DIRS = [
    "ml",
    "outputs",
    "backend",
    "src",
    "design-references",
]

# Root-level files to include, if they exist
INCLUDE_FILES = [
    "README.md",
    "README.txt",
    "package.json",
    "package-lock.json",
    "compose.yaml",
    "tsconfig.json",
    "vite.config.ts",
]

# Folders/files to exclude anywhere
EXCLUDED_DIRS = {
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    ".pytest_cache",
    ".mypy_cache",
}

EXCLUDED_FILES = {
    ".env",
    ".env.local",
    ".env.production",
}

EXCLUDED_SUFFIXES = {".pyc", ".pyo"}

# Exclude large model checkpoints to keep ZIP manageable.
# Set to False if you want to include them.
EXCLUDE_CHECKPOINTS = True

def should_exclude(path):
    if any(part in EXCLUDED_DIRS for part in path.parts):
        return True

    if path.name in EXCLUDED_FILES:
        return True

    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True

    if EXCLUDE_CHECKPOINTS and "checkpoints" in path.parts:
        return True

    return False


def create_zip():
    if not PROJECT_DIR.exists():
        print("ERROR: Project folder not found:", PROJECT_DIR)
        return

    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)

    added = 0
    total_size = 0

    with zipfile.ZipFile(
        ZIP_PATH, "w", zipfile.ZIP_DEFLATED
    ) as zip_file:

        for folder in INCLUDE_DIRS:
            folder_path = PROJECT_DIR / folder

            if not folder_path.exists():
                print("Skipped missing folder:", folder)
                continue

            for file_path in folder_path.rglob("*"):
                if not file_path.is_file():
                    continue

                relative_path = file_path.relative_to(PROJECT_DIR)

                if should_exclude(relative_path):
                    continue

                zip_file.write(
                    file_path,
                    arcname=Path(PROJECT_DIR.name) / relative_path
                )

                added += 1
                total_size += file_path.stat().st_size

        for filename in INCLUDE_FILES:
            file_path = PROJECT_DIR / filename

            if file_path.is_file() and not should_exclude(file_path):
                zip_file.write(
                    file_path,
                    arcname=Path(PROJECT_DIR.name) / filename
                )
                added += 1
                total_size += file_path.stat().st_size

    print("\nZIP CREATED SUCCESSFULLY!")
    print("Location:", ZIP_PATH)
    print("Files included:", added)
    print("Original included size:", round(total_size / (1024**2), 2), "MB")
    print("ZIP size:", round(ZIP_PATH.stat().st_size / (1024**2), 2), "MB")


if __name__ == "__main__":
    create_zip()
