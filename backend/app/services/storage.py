import hashlib
import io
import re
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError


FORMATS = {
    ".png": ("PNG", "image/png"),
    ".jpg": ("JPEG", "image/jpeg"),
    ".jpeg": ("JPEG", "image/jpeg"),
}


class InvalidImage(ValueError):
    pass


def clean_original_filename(filename: str | None) -> str:
    leaf = (filename or "image").replace("\\", "/").split("/")[-1]
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", leaf).strip()
    return (cleaned or "image")[:255]


def validate_image(content: bytes, filename: str, max_image_pixels: int = 40_000_000) -> tuple[str, str]:
    extension = Path(filename).suffix.lower()
    expected = FORMATS.get(extension)
    if expected is None:
        raise InvalidImage("Only PNG, JPG, and JPEG files are accepted")
    try:
        with Image.open(io.BytesIO(content)) as image:
            detected_format = image.format
            if image.width * image.height > max_image_pixels:
                raise InvalidImage("Image dimensions exceed the configured pixel limit")
            image.verify()
    except InvalidImage:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidImage("Uploaded content is not a valid supported image") from exc
    if detected_format != expected[0]:
        raise InvalidImage("File extension does not match the image content")
    return expected[1], extension


def store_image(
    content: bytes,
    filename: str,
    upload_directory: Path,
    max_image_pixels: int = 40_000_000,
) -> tuple[str, str, int, str]:
    media_type, extension = validate_image(content, filename, max_image_pixels)
    root = upload_directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid.uuid4().hex}{extension}"
    target = (root / storage_key).resolve()
    if target.parent != root:
        raise InvalidImage("Invalid storage target")
    with target.open("xb") as output:
        output.write(content)
    return storage_key, media_type, len(content), hashlib.sha256(content).hexdigest()


def resolve_storage_path(upload_directory: Path, storage_key: str) -> Path:
    root = upload_directory.resolve()
    target = (root / storage_key).resolve()
    if target.parent != root or Path(storage_key).name != storage_key:
        raise ValueError("Invalid storage key")
    return target
