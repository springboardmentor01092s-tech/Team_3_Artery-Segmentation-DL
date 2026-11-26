from __future__ import annotations

import numpy as np


IMAGENET_MEAN = np.asarray((0.485, 0.456, 0.406), dtype=np.float32)
IMAGENET_STD = np.asarray((0.229, 0.224, 0.225), dtype=np.float32)


def normalize_rgb_array(image_array: np.ndarray, mode: str = "none") -> np.ndarray:
    """Normalize an RGB float array already scaled to [0, 1]."""
    if mode == "none":
        return image_array
    if mode == "imagenet":
        return (image_array - IMAGENET_MEAN) / IMAGENET_STD
    raise ValueError(f"Unknown normalization mode: {mode}")
