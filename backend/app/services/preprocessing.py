"""Reusable, non-destructive image preparation for future ML consumers."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.storage import InvalidImage, validate_image


@dataclass(frozen=True)
class PreprocessingConfig:
    """Configurable baseline; target_size is specified as (width, height)."""

    target_size: tuple[int, int] = (256, 256)

    def __post_init__(self) -> None:
        if len(self.target_size) != 2 or any(size <= 0 for size in self.target_size):
            raise ValueError("target_size must contain positive width and height")


@dataclass(frozen=True)
class PreprocessingResult:
    pixels: np.ndarray
    metadata: dict[str, object]


class PreprocessingError(ValueError):
    """The stored image cannot be safely prepared by this baseline."""


def _grayscale_pixels(image: Image.Image) -> tuple[np.ndarray, int]:
    """Return grayscale pixels and the unsigned source range maximum."""
    if image.mode in {"1", "L", "P", "RGB", "RGBA", "LA", "CMYK", "YCbCr"}:
        gray = image.convert("RGB").convert("L") if image.mode != "L" and image.mode != "1" else image.convert("L")
        return np.asarray(gray, dtype=np.uint8), 255

    if image.mode.startswith("I;16") or image.mode == "I":
        pixels = np.asarray(image)
        if pixels.size == 0 or np.issubdtype(pixels.dtype, np.floating):
            raise PreprocessingError("Image pixel representation is not supported")
        if np.issubdtype(pixels.dtype, np.signedinteger):
            if int(pixels.min()) < 0 or int(pixels.max()) > 65535:
                raise PreprocessingError("Signed or out-of-range image intensities are not supported")
            pixels = pixels.astype(np.uint16)
        elif pixels.dtype != np.uint16:
            raise PreprocessingError("Image pixel representation is not supported")
        return pixels, 65535

    raise PreprocessingError(f"Image mode '{image.mode}' is not supported by the preprocessing baseline")


def preprocess_image_file(
    path: Path,
    original_filename: str,
    *,
    max_upload_size_bytes: int,
    max_image_pixels: int,
    config: PreprocessingConfig = PreprocessingConfig(),
) -> PreprocessingResult:
    """Load a validated stored image and return a normalized CHW float32 array.

    The input is read only. No preprocessed artifact is persisted.
    """
    try:
        file_size = path.stat().st_size
    except OSError as exc:
        raise PreprocessingError("Stored image file is unavailable") from exc
    if file_size > max_upload_size_bytes:
        raise PreprocessingError("Stored image exceeds the configured upload size limit")

    try:
        content = path.read_bytes()
        validate_image(content, original_filename, max_image_pixels)
        with Image.open(path) as image:
            source_width, source_height = image.size
            source_mode = image.mode
            raw_pixels, source_max = _grayscale_pixels(image)
    except InvalidImage as exc:
        raise PreprocessingError(str(exc)) from exc
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise PreprocessingError("Stored image is unreadable or corrupted") from exc

    # Pillow resizes in the source integer range; no per-image contrast stretching is applied.
    resize_mode = "I" if source_max == 65535 else "L"
    source = Image.fromarray(raw_pixels.astype(np.int32) if source_max == 65535 else raw_pixels, mode=resize_mode)
    contained = ImageOps.contain(source, config.target_size, method=Image.Resampling.LANCZOS)
    resized = np.asarray(contained, dtype=np.uint16 if source_max == 65535 else np.uint8)
    target_width, target_height = config.target_size
    output = np.zeros((target_height, target_width), dtype=np.float32)
    left = (target_width - contained.width) // 2
    top = (target_height - contained.height) // 2
    normalized = np.clip(resized.astype(np.float32) / source_max, 0.0, 1.0)
    output[top : top + contained.height, left : left + contained.width] = normalized
    chw = np.ascontiguousarray(output[np.newaxis, :, :], dtype=np.float32)

    return PreprocessingResult(
        pixels=chw,
        metadata={
            "input_width": source_width,
            "input_height": source_height,
            "source_mode": source_mode,
            "output_width": target_width,
            "output_height": target_height,
            "output_shape": [1, target_height, target_width],
            "model_batch_shape": [1, 1, target_height, target_width],
            "data_type": "float32",
            "channel_format": "CHW, one grayscale channel",
            "intensity_range": [0.0, 1.0],
            "normalization": f"unsigned source range [0, {source_max}] scaled linearly to [0, 1]; no per-image contrast normalization",
            "resize": "Lanczos fit preserving aspect ratio, centered with zero padding",
            "output_persisted": False,
        },
    )
