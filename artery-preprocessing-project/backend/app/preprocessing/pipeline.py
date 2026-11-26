from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

from app.preprocessing.exceptions import (
    ImageValidationError,
    PreprocessingParameterError,
    UnsupportedImageError,
)
from app.utils.files import SUPPORTED_EXTENSIONS

try:
    import pydicom
    from pydicom.errors import InvalidDicomError
except ImportError:  # pragma: no cover
    pydicom = None
    InvalidDicomError = Exception


RASTER_EXTENSIONS = {".png", ".jpg", ".jpeg"}
DICOM_EXTENSIONS = {".dcm", ".dicom"}


@dataclass
class LoadedImage:
    array: np.ndarray
    format: str
    width: int
    height: int
    metadata: dict = field(default_factory=dict)
    is_dicom: bool = False


def validate_image(path: Path, max_bytes: int) -> None:
    if not path.exists() or not path.is_file():
        raise ImageValidationError("File was not found or is not a readable file.")
    size = path.stat().st_size
    if size <= 0:
        raise ImageValidationError("File is empty.")
    if size > max_bytes:
        raise ImageValidationError("File exceeds the configured size limit.")
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedImageError("Unsupported file type.")


def _apply_photometric(arr: np.ndarray, photometric: str | None) -> np.ndarray:
    if photometric and photometric.upper() == "MONOCHROME1":
        return arr.max() - arr
    return arr


def _dicom_pixel_spacing_metadata(ds) -> dict:
    """Retain syntactically valid DICOM PixelSpacing without asserting calibration validity."""
    raw_spacing = getattr(ds, "PixelSpacing", None)
    calibration_type = getattr(ds, "PixelSpacingCalibrationType", None)
    calibration_type = str(calibration_type).strip() if calibration_type is not None else None
    if calibration_type == "":
        calibration_type = None

    spacing = None
    status = "unavailable"
    if raw_spacing is not None:
        try:
            values = [float(value) for value in raw_spacing]
            if len(values) == 2 and all(math.isfinite(value) and value > 0 for value in values):
                spacing = values
                status = "reported_valid_values"
            else:
                status = "invalid_values"
        except (TypeError, ValueError, OverflowError):
            status = "invalid_values"

    return {
        "pixel_spacing": spacing,
        "pixel_spacing_status": status,
        "pixel_spacing_calibration_type": calibration_type,
        "pixel_spacing_unit": "mm_per_pixel" if spacing is not None else None,
        "pixel_spacing_order": "row_column" if spacing is not None else None,
    }


def _load_dicom(path: Path) -> LoadedImage:
    if pydicom is None:
        raise UnsupportedImageError("DICOM support is unavailable in this environment.")
    try:
        ds = pydicom.dcmread(str(path), force=False)
    except InvalidDicomError as exc:
        raise ImageValidationError("File is not a valid DICOM object.") from exc
    except Exception as exc:
        raise ImageValidationError("DICOM file could not be read.") from exc

    frames = int(getattr(ds, "NumberOfFrames", 1) or 1)
    if frames > 1:
        raise UnsupportedImageError("Multi-frame or volumetric DICOM is not supported in this prototype.")
    if not hasattr(ds, "pixel_array"):
        raise ImageValidationError("DICOM file does not contain pixel data.")

    try:
        arr = ds.pixel_array
    except Exception as exc:
        raise ImageValidationError("DICOM pixel data could not be decoded.") from exc

    if arr.ndim == 3 and arr.shape[0] > 1 and arr.shape[-1] not in (1, 3, 4):
        raise UnsupportedImageError("Unsupported DICOM dimensionality for this prototype.")
    if arr.ndim == 3 and arr.shape[-1] in (3, 4):
        pass
    elif arr.ndim == 3:
        arr = arr[0]
    if arr.ndim > 3:
        raise UnsupportedImageError("Unsupported DICOM dimensionality for this prototype.")

    slope = float(getattr(ds, "RescaleSlope", 1) or 1)
    intercept = float(getattr(ds, "RescaleIntercept", 0) or 0)
    arr = arr.astype(np.float32) * slope + intercept
    photometric = str(getattr(ds, "PhotometricInterpretation", "") or "")
    arr = _apply_photometric(arr, photometric)

    metadata = {
        "modality": str(getattr(ds, "Modality", "") or ""),
        "photometric_interpretation": photometric,
        **_dicom_pixel_spacing_metadata(ds),
        "bits_stored": int(getattr(ds, "BitsStored", 0) or 0) or None,
        "rescale_slope": slope,
        "rescale_intercept": intercept,
        "transfer_syntax": str(getattr(ds, "file_meta", None) and getattr(ds.file_meta, "TransferSyntaxUID", "") or ""),
        "note": "Original DICOM file is preserved unchanged. Display conversion happens on a working copy only.",
    }
    height, width = int(arr.shape[0]), int(arr.shape[1])
    if width < 8 or height < 8:
        raise ImageValidationError("Image dimensions are too small to process.")
    return LoadedImage(
        array=arr,
        format="DICOM",
        width=width,
        height=height,
        metadata=metadata,
        is_dicom=True,
    )


def _load_raster(path: Path) -> LoadedImage:
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            img.load()
            mode = img.mode
            if mode not in {"L", "RGB", "RGBA", "I;16", "I"}:
                img = img.convert("RGB")
                mode = "RGB"
            arr = np.array(img)
            width, height = img.size
            fmt = (img.format or path.suffix.replace(".", "")).upper()
    except UnidentifiedImageError as exc:
        raise ImageValidationError("File is not a readable raster image.") from exc
    except Exception as exc:
        raise ImageValidationError("Image could not be read.") from exc

    if arr.size == 0:
        raise ImageValidationError("Image contains no pixel data.")
    if width < 8 or height < 8:
        raise ImageValidationError("Image dimensions are too small to process.")
    return LoadedImage(
        array=arr,
        format=fmt,
        width=width,
        height=height,
        metadata={"color_mode": mode, "note": "Raster image loaded as a working copy."},
        is_dicom=False,
    )


def load_image(path: Path) -> LoadedImage:
    suffix = path.suffix.lower()
    if suffix in DICOM_EXTENSIONS:
        return _load_dicom(path)
    if suffix in RASTER_EXTENSIONS:
        return _load_raster(path)
    raise UnsupportedImageError("Unsupported file type.")


def normalize_intensity(array: np.ndarray, method: str = "minmax") -> np.ndarray:
    working = array.astype(np.float32)
    if method in {"none", None}:
        return working
    if method == "minmax":
        min_v = float(np.min(working))
        max_v = float(np.max(working))
        if max_v - min_v < 1e-8:
            return np.zeros_like(working)
        return (working - min_v) / (max_v - min_v)
    if method == "zscore":
        mean = float(np.mean(working))
        std = float(np.std(working))
        if std < 1e-8:
            return np.zeros_like(working)
        return (working - mean) / std
    raise PreprocessingParameterError("Unknown intensity normalization method.")


def resize_image(
    array: np.ndarray,
    target_width: int,
    target_height: int,
    preserve_aspect_ratio: bool = True,
) -> np.ndarray:
    if target_width < 1 or target_height < 1:
        raise PreprocessingParameterError("Target dimensions must be positive.")
    h, w = array.shape[:2]
    if preserve_aspect_ratio:
        scale = min(target_width / w, target_height / h)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
    else:
        new_w, new_h = target_width, target_height
    interpolation = cv2.INTER_AREA if (new_w < w or new_h < h) else cv2.INTER_LINEAR
    return cv2.resize(array, (new_w, new_h), interpolation=interpolation)


def _to_gray_u8(array: np.ndarray) -> np.ndarray:
    if array.ndim == 3:
        if array.shape[2] == 4:
            array = cv2.cvtColor(array.astype(np.uint8), cv2.COLOR_RGBA2GRAY)
        elif array.shape[2] == 3:
            array = cv2.cvtColor(_display_u8(array), cv2.COLOR_RGB2GRAY)
        else:
            array = array[:, :, 0]
    working = array.astype(np.float32)
    min_v, max_v = float(np.min(working)), float(np.max(working))
    if max_v - min_v < 1e-8:
        return np.zeros(working.shape, dtype=np.uint8)
    scaled = (working - min_v) / (max_v - min_v)
    return (scaled * 255.0).clip(0, 255).astype(np.uint8)


def _display_u8(array: np.ndarray) -> np.ndarray:
    working = array.astype(np.float32)
    min_v, max_v = float(np.min(working)), float(np.max(working))
    if max_v - min_v < 1e-8:
        scaled = np.zeros_like(working)
    else:
        scaled = (working - min_v) / (max_v - min_v)
    u8 = (scaled * 255.0).clip(0, 255).astype(np.uint8)
    if u8.ndim == 2:
        return u8
    if u8.shape[2] == 4:
        return cv2.cvtColor(u8, cv2.COLOR_RGBA2RGB)
    return u8


def reduce_noise(array: np.ndarray, method: str = "gaussian", ksize: int = 3) -> np.ndarray:
    if method in {"none", None}:
        return array
    k = ksize if ksize % 2 == 1 else ksize + 1
    display = _display_u8(array)
    if method == "gaussian":
        filtered = cv2.GaussianBlur(display, (k, k), 0)
    elif method == "median":
        filtered = cv2.medianBlur(display, k)
    else:
        raise PreprocessingParameterError("Unknown noise-reduction method.")
    return filtered.astype(np.float32) / 255.0


def enhance_contrast(array: np.ndarray, method: str = "clahe", clip_limit: float = 2.0, tile_size: int = 8) -> np.ndarray:
    if method in {"none", None}:
        return array
    if method != "clahe":
        raise PreprocessingParameterError("Unknown contrast-enhancement method.")
    gray = _to_gray_u8(array)
    clahe = cv2.createCLAHE(clipLimit=float(clip_limit), tileGridSize=(tile_size, tile_size))
    enhanced = clahe.apply(gray)
    return enhanced.astype(np.float32) / 255.0


def save_processed_image(array: np.ndarray, destination: Path) -> tuple[int, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    display = _display_u8(array)
    ok = cv2.imwrite(str(destination), display if display.ndim == 2 else cv2.cvtColor(display, cv2.COLOR_RGB2BGR))
    if not ok:
        raise ImageValidationError("Processed image could not be saved.")
    h, w = display.shape[:2]
    return w, h


def preprocess_image(
    source_path: Path,
    destination_path: Path,
    max_bytes: int,
    params: dict,
) -> dict:
    validate_image(source_path, max_bytes)
    loaded = load_image(source_path)
    working = loaded.array.copy()
    operations: list[dict] = []

    if params.get("normalize") and params.get("normalize_method") != "none":
        working = normalize_intensity(working, params.get("normalize_method", "minmax"))
        operations.append({"name": "normalize_intensity", "method": params.get("normalize_method", "minmax")})

    if params.get("resize"):
        tw = int(params.get("target_width") or 512)
        th = int(params.get("target_height") or 512)
        preserve = bool(params.get("preserve_aspect_ratio", True))
        working = resize_image(working, tw, th, preserve)
        operations.append(
            {
                "name": "resize_image",
                "target_width": tw,
                "target_height": th,
                "preserve_aspect_ratio": preserve,
                "note": "Exact resize is used only when preserve_aspect_ratio is false.",
            }
        )

    if params.get("denoise") and params.get("denoise_method") != "none":
        if loaded.is_dicom and loaded.metadata.get("modality") in {"PT", "NM"}:
            raise PreprocessingParameterError(
                "Noise reduction is disabled for this DICOM modality because it can hide clinically relevant intensity variation."
            )
        working = reduce_noise(working, params.get("denoise_method", "gaussian"), int(params.get("denoise_ksize", 3)))
        operations.append(
            {
                "name": "reduce_noise",
                "method": params.get("denoise_method", "gaussian"),
                "ksize": int(params.get("denoise_ksize", 3)),
            }
        )

    if params.get("contrast") and params.get("contrast_method") != "none":
        if loaded.is_dicom:
            operations.append(
                {
                    "name": "enhance_contrast",
                    "method": "clahe",
                    "note": "CLAHE is applied to a display-normalized copy, not to the archived original DICOM.",
                }
            )
        working = enhance_contrast(
            working,
            params.get("contrast_method", "clahe"),
            float(params.get("clahe_clip_limit", 2.0)),
            int(params.get("clahe_tile_size", 8)),
        )
        if not loaded.is_dicom:
            operations.append(
                {
                    "name": "enhance_contrast",
                    "method": "clahe",
                    "clip_limit": float(params.get("clahe_clip_limit", 2.0)),
                    "tile_size": int(params.get("clahe_tile_size", 8)),
                }
            )

    processed_w, processed_h = save_processed_image(working, destination_path)
    sidecar = destination_path.with_suffix(".json")
    sidecar.write_text(
        json.dumps(
            {
                "source_format": loaded.format,
                "original_metadata": loaded.metadata,
                "operations": operations,
                "disclaimer": "Preprocessing prepares images for later analysis. It does not detect stenosis or provide a diagnosis.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "input_format": loaded.format,
        "original_width": loaded.width,
        "original_height": loaded.height,
        "processed_width": processed_w,
        "processed_height": processed_h,
        "operations": operations,
        "metadata": loaded.metadata,
    }
