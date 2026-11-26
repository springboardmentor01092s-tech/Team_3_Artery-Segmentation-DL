from __future__ import annotations

import cv2
import numpy as np


def binarize(probability: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    return (probability >= threshold).astype(np.uint8)


def filter_small_components(binary: np.ndarray, min_area: int = 5) -> np.ndarray:
    mask = (binary > 0).astype(np.uint8)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    kept = np.zeros_like(mask)
    for label in range(1, num):
        if stats[label, cv2.CC_STAT_AREA] >= min_area:
            kept[labels == label] = 1
    return kept


