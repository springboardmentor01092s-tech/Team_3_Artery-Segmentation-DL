from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import torch
import json

from .engine import get_device, load_checkpoint, predict_image
from .explain import draw_boxes, encode_png, overlay_mask, probability_heatmap
from .localize import extract_candidates
from .paths import checkpoints_dir, reports_dir
from .postprocess import binarize, filter_small_components

LIMITATIONS = [
    "ARCADE stenosis labels are lesion polygons and boxes, not lumen diameters.",
    "Percentage narrowing is not computed because reference and minimum lumen diameters are unavailable.",
    "Severity grades (mild/moderate/severe) are not present in the dataset and are not invented.",
    "Candidate mean predicted probability is not a separate classifier score or clinical confidence.",
    "Overlays and probability heatmaps are segmentation explanations, not Grad-CAM.",
    "The dataset audit found one exact stenosis train/validation image duplicate; future training excludes the training copy, but exposure of existing checkpoints cannot be confirmed from available provenance.",
    "This is an academic prototype, not a clinical diagnostic device.",
]

DIAMETER_MEASUREMENT_UNAVAILABLE = {
    "measurement_status": "unavailable",
    "reference_vessel_diameter_mm": None,
    "minimum_lumen_diameter_mm": None,
    "reference_vessel_diameter_px": None,
    "minimum_lumen_diameter_px": None,
    "stenosis_percentage": None,
    "measurement_location": None,
    "reference_location_xy": None,
    "minimum_location_xy": None,
    "diameter_unit": None,
    "quality": "unavailable",
    "reason": (
        "Unable to calculate: the active model segments stenosis lesion regions, not vessel lumen boundaries. "
        "A validated reference segment, minimum-lumen cross-section, and image calibration are unavailable."
    ),
}


def default_checkpoint() -> Path:
    preferred = [
        checkpoints_dir() / "best_stenosis_unet_optimized.pth",
        checkpoints_dir() / "best_resunet_04b.pth",
        checkpoints_dir() / "stenosis_attention_unet_256.pth",
    ]
    for path in preferred:
        if path.exists():
            return path
    raise FileNotFoundError(
        "No stenosis checkpoint found under backend/checkpoints. "
        "Set MODEL_CHECKPOINT to a compatible trained .pth file."
    )


class StenosisAnalyzer:
    def __init__(self, checkpoint: Path | None = None, device: torch.device | None = None):
        self.device = device or get_device()
        self.checkpoint_path = Path(checkpoint) if checkpoint else default_checkpoint()
        self.model, self.meta = load_checkpoint(self.checkpoint_path, self.device)
        self.image_size = int(self.meta.get("image_size", 256))
        self.threshold = float(self.meta.get("threshold", 0.5))
        self.threshold_source = "checkpoint_metadata" if "threshold" in self.meta else "default_0.5"
        threshold_file = self.checkpoint_path.with_suffix(self.checkpoint_path.suffix + ".threshold.json")
        if threshold_file.is_file():
            configured = json.loads(threshold_file.read_text(encoding="utf-8"))
            selected = float(configured["threshold"])
            if not 0.0 < selected < 1.0:
                raise ValueError(f"Threshold in {threshold_file.name} must be between 0 and 1.")
            self.threshold = selected
            self.threshold_source = configured.get("selection_method", "validation_sidecar")
        self.loaded = True

    def info(self) -> dict:
        info = {
            "checkpoint": str(self.checkpoint_path),
            "exists": self.checkpoint_path.exists(),
            "architecture": self.meta.get("resolved_architecture"),
            "image_size": self.image_size,
            "threshold": self.threshold,
            "threshold_source": self.threshold_source,
            "device": str(self.device),
            "val_dice": self.meta.get("val_dice") or self.meta.get("best_val_dice"),
            "val_iou": self.meta.get("val_iou"),
            "epoch": self.meta.get("epoch"),
            "experiment_04b_present": (checkpoints_dir() / "best_resunet_04b.pth").exists(),
            "limitations": LIMITATIONS,
        }
        validation_root = reports_dir() / "model_validation"
        validation_path = validation_root / f"validation_metrics_{self.checkpoint_path.stem}.json"
        if not validation_path.is_file() and self.checkpoint_path.name == "best_stenosis_unet_optimized.pth":
            validation_path = validation_root / "validation_metrics.json"
        if validation_path.is_file():
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
            info["validation"] = {
                "split": validation.get("dataset_split"),
                "samples": validation.get("samples_evaluated"),
                "threshold": validation.get("selected_threshold"),
                "metrics": validation.get("selected_threshold_metrics"),
                "test_split_used_for_tuning": validation.get("test_split_used_for_tuning"),
                "source": validation_path.name,
            }
            info["val_dice"] = info["validation"]["metrics"]["per_image_macro"]["dice"]
            info["val_iou"] = info["validation"]["metrics"]["per_image_macro"]["iou"]
            info["validation_metric_origin"] = "recomputed_on_full_validation_split"
        return info

    def analyze(
        self,
        image_bgr: np.ndarray,
        threshold: float | None = None,
        min_area: int = 20,
    ) -> dict:
        if image_bgr.ndim == 2:
            image_bgr = cv2.cvtColor(image_bgr, cv2.COLOR_GRAY2BGR)
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        probability = predict_image(self.model, rgb, self.image_size, self.device,
                                    normalization=self.meta.get("normalization", "none"))
        thr = self.threshold if threshold is None else float(threshold)
        binary = filter_small_components(binarize(probability, thr), min_area=min_area)
        candidates = extract_candidates(binary, probability, min_area=min_area)
        overlay = overlay_mask(image_bgr, binary)
        boxed = draw_boxes(overlay, candidates)
        heat = probability_heatmap(image_bgr, probability)
        return {
            "probability": probability,
            "binary_mask": binary,
            "candidates": candidates,
            "threshold": thr,
            "min_area": min_area,
            "n_candidates": len(candidates),
            "foreground_pixels": int(binary.sum()),
            "images": {
                "overlay_png": encode_png(overlay),
                "boxes_png": encode_png(boxed),
                "heatmap_png": encode_png(heat),
                "mask_png": encode_png((binary * 255).astype(np.uint8)),
            },
            "percentage_narrowing": None,
            "severity": None,
            "diameter_measurement": dict(DIAMETER_MEASUREMENT_UNAVAILABLE),
            "limitations": LIMITATIONS,
            "model": self.info(),
        }
