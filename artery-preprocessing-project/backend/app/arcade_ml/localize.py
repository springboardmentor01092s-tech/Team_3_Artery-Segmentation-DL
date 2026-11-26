from __future__ import annotations

import cv2
import numpy as np

from .metrics import box_iou


def extract_candidates(
    binary_mask: np.ndarray,
    probability: np.ndarray | None = None,
    min_area: int = 20,
) -> list[dict]:
    mask_u8 = (binary_mask > 0).astype(np.uint8)
    num, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_u8, connectivity=8)
    candidates = []
    for label in range(1, num):
        x, y, w, h, area = stats[label]
        if int(area) < min_area:
            continue
        component = labels == label
        conf = None
        if probability is not None:
            conf = float(probability[component].mean())
        candidates.append(
            {
                "id": int(label),
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h),
                "pixel_area": int(area),
                "centroid_x": float(centroids[label][0]),
                "centroid_y": float(centroids[label][1]),
                "mean_predicted_probability": conf,
                "score_semantics": "mean_predicted_segmentation_probability" if conf is not None else None,
            }
        )
    candidates.sort(key=lambda c: (c["mean_predicted_probability"] is not None, c["mean_predicted_probability"] or 0, c["pixel_area"]), reverse=True)
    return candidates


def match_localization(
    predicted: list[dict],
    ground_truth: list[dict],
    iou_threshold: float = 0.3,
) -> dict:
    used_gt = set()
    tp = 0
    matches = []
    for pred in predicted:
        best_iou = 0.0
        best_j = None
        for j, gt in enumerate(ground_truth):
            if j in used_gt:
                continue
            iou = box_iou(pred, gt)
            if iou > best_iou:
                best_iou = iou
                best_j = j
        if best_j is not None and best_iou >= iou_threshold:
            used_gt.add(best_j)
            tp += 1
            matches.append({"pred_id": pred.get("id"), "gt_index": best_j, "iou": best_iou})
    fp = len(predicted) - tp
    fn = len(ground_truth) - tp
    precision = tp / (tp + fp + 1e-7)
    recall = tp / (tp + fn + 1e-7)
    f1 = 2 * precision * recall / (precision + recall + 1e-7)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "iou_threshold": iou_threshold,
        "matches": matches,
    }
