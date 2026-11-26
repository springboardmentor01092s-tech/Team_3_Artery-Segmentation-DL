from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass
class PreprocessSettings:
    resize_width: int = 512
    resize_height: int = 512
    keep_aspect: bool = True
    denoise: bool = True
    gaussian_ksize: int = 3
    clahe: bool = True
    clahe_clip: float = 2.0
    clahe_tile: int = 8
    normalize: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    if image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def apply_preprocess(image_bgr: np.ndarray, settings: PreprocessSettings) -> tuple[np.ndarray, dict]:
    original_h, original_w = image_bgr.shape[:2]
    gray = _to_gray(image_bgr)
    processed = gray.copy()
    notes = []

    if settings.denoise and settings.gaussian_ksize >= 3:
        k = settings.gaussian_ksize if settings.gaussian_ksize % 2 == 1 else settings.gaussian_ksize + 1
        processed = cv2.GaussianBlur(processed, (k, k), 0)
        notes.append(f"gaussian_blur k={k}")

    if settings.clahe:
        tile = max(1, int(settings.clahe_tile))
        clahe = cv2.createCLAHE(clipLimit=float(settings.clahe_clip), tileGridSize=(tile, tile))
        processed = clahe.apply(processed)
        notes.append(f"clahe clip={settings.clahe_clip} tile={tile}")

    if settings.normalize:
        processed = cv2.normalize(processed, None, 0, 255, cv2.NORM_MINMAX)
        notes.append("minmax_normalize")

    target_w = max(16, int(settings.resize_width))
    target_h = max(16, int(settings.resize_height))
    if settings.keep_aspect:
        scale = min(target_w / original_w, target_h / original_h)
        new_w = max(1, int(round(original_w * scale)))
        new_h = max(1, int(round(original_h * scale)))
        resized = cv2.resize(processed, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((target_h, target_w), dtype=np.uint8)
        y0 = (target_h - new_h) // 2
        x0 = (target_w - new_w) // 2
        canvas[y0 : y0 + new_h, x0 : x0 + new_w] = resized
        processed = canvas
        notes.append(f"letterbox {new_w}x{new_h} onto {target_w}x{target_h}")
    else:
        processed = cv2.resize(processed, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        notes.append(f"resize {target_w}x{target_h}")

    rgb = cv2.cvtColor(processed, cv2.COLOR_GRAY2BGR)
    info = {
        "original_width": original_w,
        "original_height": original_h,
        "output_width": rgb.shape[1],
        "output_height": rgb.shape[0],
        "operations": notes,
        "settings": settings.to_dict(),
    }
    return rgb, info


def quality_checks(image_bgr: np.ndarray) -> dict:
    gray = _to_gray(image_bgr)
    mean = float(np.mean(gray))
    std = float(np.std(gray))
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return {
        "width": int(image_bgr.shape[1]),
        "height": int(image_bgr.shape[0]),
        "channels": 1 if image_bgr.ndim == 2 else int(image_bgr.shape[2]),
        "mean_intensity": round(mean, 3),
        "std_intensity": round(std, 3),
        "laplacian_variance": round(blur, 3),
        "possibly_blank": std < 1.0,
        "possibly_blurry": blur < 20.0,
    }
