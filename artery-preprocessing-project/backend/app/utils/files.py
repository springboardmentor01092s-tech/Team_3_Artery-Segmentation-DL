import re
import uuid
from pathlib import Path

SAFE_NAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".dcm", ".dicom"}


def sanitize_original_filename(name: str) -> str:
    basename = Path(name).name
    cleaned = SAFE_NAME_PATTERN.sub("_", basename).strip("._")
    return cleaned[:180] or "upload"


def unique_storage_name(original_name: str) -> str:
    suffix = Path(original_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        suffix = ".bin"
    return f"{uuid.uuid4().hex}{suffix}"


def resolve_inside(base: Path, filename: str) -> Path:
    candidate = (base / Path(filename).name).resolve()
    base_resolved = base.resolve()
    if base_resolved not in candidate.parents and candidate != base_resolved:
        raise ValueError("Unsafe file path.")
    return candidate
