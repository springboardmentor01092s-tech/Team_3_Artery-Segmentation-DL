from __future__ import annotations

import numpy as np
import torch


def hard_metrics(logits: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5) -> dict[str, float]:
    preds = (torch.sigmoid(logits) >= threshold).float()
    dims = (1, 2, 3)
    tp = (preds * targets).sum(dim=dims)
    fp = (preds * (1 - targets)).sum(dim=dims)
    fn = ((1 - preds) * targets).sum(dim=dims)
    tn = ((1 - preds) * (1 - targets)).sum(dim=dims)
    dice = (2 * tp + 1e-7) / (2 * tp + fp + fn + 1e-7)
    iou = (tp + 1e-7) / (tp + fp + fn + 1e-7)
    precision = (tp + 1e-7) / (tp + fp + 1e-7)
    recall = (tp + 1e-7) / (tp + fn + 1e-7)
    return {
        "dice": float(dice.mean().item()),
        "iou": float(iou.mean().item()),
        "precision": float(precision.mean().item()),
        "recall": float(recall.mean().item()),
        "tp": float(tp.sum().item()),
        "fp": float(fp.sum().item()),
        "fn": float(fn.sum().item()),
        "tn": float(tn.sum().item()),
    }


def numpy_metrics(pred: np.ndarray, truth: np.ndarray, threshold: float = 0.5) -> dict[str, float]:
    p = (pred >= threshold).astype(np.uint8)
    t = (truth > 0).astype(np.uint8)
    tp = float(np.logical_and(p == 1, t == 1).sum())
    fp = float(np.logical_and(p == 1, t == 0).sum())
    fn = float(np.logical_and(p == 0, t == 1).sum())
    tn = float(np.logical_and(p == 0, t == 0).sum())
    dice = (2 * tp + 1e-7) / (2 * tp + fp + fn + 1e-7)
    iou = (tp + 1e-7) / (tp + fp + fn + 1e-7)
    precision = (tp + 1e-7) / (tp + fp + 1e-7)
    recall = (tp + 1e-7) / (tp + fn + 1e-7)
    return {
        "dice": dice,
        "iou": iou,
        "precision": precision,
        "recall": recall,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def box_iou(a: dict, b: dict) -> float:
    ax1, ay1 = a["x"], a["y"]
    ax2, ay2 = a["x"] + a["width"], a["y"] + a["height"]
    bx1, by1 = b["x"], b["y"]
    bx2, by2 = b["x"] + b["width"], b["y"] + b["height"]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    union = a["width"] * a["height"] + b["width"] * b["height"] - inter
    if union <= 0:
        return 0.0
    return inter / union
