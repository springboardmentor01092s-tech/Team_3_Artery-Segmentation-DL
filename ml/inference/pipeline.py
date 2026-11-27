"""Combined, non-clinical artery and stenosis segmentation inference pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, UnidentifiedImageError

from ml.inference.attention_unet import AttentionUNetAdapter
from ml.inference.percentage_narrowing import estimate_percentage_narrowing, unavailable_percentage_narrowing
from ml.inference.unetpp import GRADCAM_METHOD, GRADCAM_TARGET_LAYER, UNetPPAdapter


ImageInput = str | Path | Image.Image


class PipelineInputError(ValueError):
    """The source image is not readable as a grayscale angiography image."""


@dataclass(frozen=True)
class StenosisCandidate:
    """A connected predicted region, not a confirmed stenosis finding."""

    candidate_id: int
    label: str
    bbox: tuple[int, int, int, int]  # x, y, width, height in original-image coordinates.
    centroid: tuple[float, float]  # x, y in original-image coordinates.
    area_pixels: int  # Counted on the U-Net++ model grid (512x512).
    mean_probability: float
    model_bbox: tuple[int, int, int, int]
    model_centroid: tuple[float, float]


@dataclass(frozen=True)
class PipelineResult:
    """Original image, aligned model outputs, candidates and display visualizations."""

    original_image: np.ndarray  # uint8 grayscale [H, W].
    artery_mask: np.ndarray  # uint8 binary [H, W].
    stenosis_probability_map: np.ndarray  # float32 [H, W].
    stenosis_mask: np.ndarray  # uint8 binary [H, W].
    candidates: tuple[StenosisCandidate, ...]
    percentage_narrowing: dict[str, Any]
    candidate_overlay: np.ndarray  # uint8 RGB [H, W, 3].
    combined_visualization: np.ndarray  # uint8 RGB montage, display-scaled.
    gradcam_heatmap: np.ndarray | None  # Optional float32 normalized [512, 512].
    model_times: dict[str, float]
    metadata: dict[str, Any]


def _read_original(image: ImageInput) -> np.ndarray:
    try:
        if isinstance(image, (str, Path)):
            with Image.open(image) as opened:
                gray = opened.convert("L")
                gray.load()
        elif isinstance(image, Image.Image):
            gray = image.convert("L")
            gray.load()
        else:
            raise PipelineInputError("image must be a filesystem path or a PIL image")
        original = np.asarray(gray, dtype=np.uint8).copy()
    except PipelineInputError:
        raise
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise PipelineInputError("image is unreadable or corrupted") from exc

    if original.ndim != 2 or not original.size or min(original.shape) <= 0:
        raise PipelineInputError("image must decode to a non-empty grayscale image")
    return original


def _single_channel(array: np.ndarray, name: str) -> np.ndarray:
    value = np.asarray(array)
    if value.ndim == 3 and value.shape[0] == 1:
        value = value[0]
    if value.ndim != 2:
        raise ValueError(f"{name} must be a single-channel 2D array or CHW array")
    return value


def _measurement_provenance(artery_metadata: dict[str, Any], stenosis_metadata: dict[str, Any], fallback_threshold: float) -> tuple[dict[str, str], dict[str, float]]:
    def threshold(metadata: dict[str, Any], fallback: float) -> float:
        try:
            value = float(metadata.get("threshold", fallback))
        except (TypeError, ValueError):
            return fallback
        return value if math.isfinite(value) and 0.0 <= value <= 1.0 else fallback

    return (
        {
            "artery": str(artery_metadata.get("model_id", "attention_unet")),
            "stenosis": str(stenosis_metadata.get("model_id", "unetpp_resnet34_stenosis")),
        },
        {
            "artery": threshold(artery_metadata, 0.50),
            "stenosis": threshold(stenosis_metadata, fallback_threshold),
        },
    )


def _connected_components(
    mask: np.ndarray,
    probabilities: np.ndarray,
) -> list[tuple[int, int, int, int, int, float, float, float]]:
    """Return x, y, w, h, area, centroid_x, centroid_y, mean_probability per component."""
    try:
        import cv2  # Optional in this isolated environment.
    except ImportError:
        cv2 = None

    if cv2 is not None:
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        component_ids = np.arange(1, count, dtype=np.int32)
        if not len(component_ids):
            return []
        areas = stats[1:, cv2.CC_STAT_AREA]
        keep = areas > 0
        sum_prob = np.bincount(labels.ravel(), weights=probabilities.ravel(), minlength=count)
        rows = []
        for label_id, area in zip(component_ids[keep], areas[keep]):
            x, y, width, height, _ = stats[label_id]
            rows.append((
                int(x), int(y), int(width), int(height), int(area),
                float(centroids[label_id, 0]), float(centroids[label_id, 1]),
                float(sum_prob[label_id] / area),
            ))
        return rows

    # Small dependency-free two-pass 8-connected labeling fallback.
    height, width = mask.shape
    labels = np.zeros((height, width), dtype=np.int32)
    parent = [0]
    rank = [0]

    def find(label: int) -> int:
        root = label
        while parent[root] != root:
            root = parent[root]
        while parent[label] != label:
            next_label = parent[label]
            parent[label] = root
            label = next_label
        return root

    def union(left: int, right: int) -> int:
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return left_root
        if rank[left_root] < rank[right_root]:
            left_root, right_root = right_root, left_root
        parent[right_root] = left_root
        if rank[left_root] == rank[right_root]:
            rank[left_root] += 1
        return left_root

    foreground_y, foreground_x = np.nonzero(mask)
    for y, x in zip(foreground_y.tolist(), foreground_x.tolist()):
        neighbors: list[int] = []
        if x > 0 and labels[y, x - 1]:
            neighbors.append(int(labels[y, x - 1]))
        if y > 0:
            if x > 0 and labels[y - 1, x - 1]:
                neighbors.append(int(labels[y - 1, x - 1]))
            if labels[y - 1, x]:
                neighbors.append(int(labels[y - 1, x]))
            if x + 1 < width and labels[y - 1, x + 1]:
                neighbors.append(int(labels[y - 1, x + 1]))
        if not neighbors:
            label = len(parent)
            parent.append(label)
            rank.append(0)
            labels[y, x] = label
        else:
            label = find(neighbors[0])
            for other in neighbors[1:]:
                label = union(label, other)
            labels[y, x] = label

    if not len(foreground_y):
        return []
    roots = np.fromiter((find(int(labels[y, x])) for y, x in zip(foreground_y, foreground_x)), dtype=np.int32)
    root_ids, inverse = np.unique(roots, return_inverse=True)
    areas = np.bincount(inverse)
    x_sums = np.bincount(inverse, weights=foreground_x)
    y_sums = np.bincount(inverse, weights=foreground_y)
    prob_sums = np.bincount(inverse, weights=probabilities[foreground_y, foreground_x])
    min_x = np.full(len(root_ids), width, dtype=np.int64)
    min_y = np.full(len(root_ids), height, dtype=np.int64)
    max_x = np.full(len(root_ids), -1, dtype=np.int64)
    max_y = np.full(len(root_ids), -1, dtype=np.int64)
    np.minimum.at(min_x, inverse, foreground_x)
    np.minimum.at(min_y, inverse, foreground_y)
    np.maximum.at(max_x, inverse, foreground_x)
    np.maximum.at(max_y, inverse, foreground_y)

    return [
        (
            int(min_x[i]), int(min_y[i]), int(max_x[i] - min_x[i] + 1), int(max_y[i] - min_y[i] + 1),
            int(areas[i]), float(x_sums[i] / areas[i]), float(y_sums[i] / areas[i]),
            float(prob_sums[i] / areas[i]),
        )
        for i in range(len(root_ids))
    ]


def extract_candidates(
    mask: np.ndarray,
    probabilities: np.ndarray,
    *,
    minimum_area: int = 5,
) -> list[dict[str, Any]]:
    """Extract 8-connected predicted regions; area/probability use the model grid."""
    if minimum_area < 1:
        raise ValueError("minimum_area must be at least 1 pixel")
    binary = _single_channel(mask, "mask")
    probability_map = _single_channel(probabilities, "probabilities")
    if binary.shape != probability_map.shape:
        raise ValueError("mask and probability map must have matching shapes")
    if not np.isin(binary, (0, 1)).all():
        raise ValueError("mask must contain only binary values 0 and 1")
    probability_map = np.asarray(probability_map, dtype=np.float32)
    if not np.isfinite(probability_map).all() or np.any((probability_map < 0) | (probability_map > 1)):
        raise ValueError("probabilities must be finite values in [0, 1]")

    components = _connected_components(
        np.ascontiguousarray(binary, dtype=np.uint8),
        probability_map,
    )

    candidates: list[dict[str, Any]] = []
    for x, y, width, height, area, cx, cy, mean_probability in components:
        if area < minimum_area:
            continue
        candidate_id = len(candidates) + 1
        candidates.append({
            "candidate_id": candidate_id,
            "label": f"Predicted stenosis candidate {candidate_id}",
            "model_bbox": (x, y, width, height),
            "model_centroid": (cx, cy),
            "area_pixels": area,
            "mean_probability": mean_probability,
        })
    return candidates


def _resize_mask(mask: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    image = Image.fromarray(np.asarray(mask, dtype=np.uint8), mode="L")
    return np.asarray(image.resize(size, Image.Resampling.NEAREST), dtype=np.uint8)


def _resize_probabilities(probabilities: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    image = Image.fromarray(np.asarray(probabilities, dtype=np.float32), mode="F")
    resized = np.asarray(image.resize(size, Image.Resampling.BILINEAR), dtype=np.float32)
    return np.clip(resized, 0.0, 1.0)


def _scale_candidates(
    model_candidates: list[dict[str, Any]],
    *,
    model_size: tuple[int, int],
    original_size: tuple[int, int],
) -> tuple[StenosisCandidate, ...]:
    model_width, model_height = model_size
    original_width, original_height = original_size
    scale_x, scale_y = original_width / model_width, original_height / model_height
    scaled = []
    for item in model_candidates:
        x, y, width, height = item["model_bbox"]
        cx, cy = item["model_centroid"]
        left = min(original_width - 1, max(0, round(x * scale_x)))
        top = min(original_height - 1, max(0, round(y * scale_y)))
        right = min(original_width, max(left + 1, round((x + width) * scale_x)))
        bottom = min(original_height, max(top + 1, round((y + height) * scale_y)))
        scaled.append(StenosisCandidate(
            candidate_id=item["candidate_id"],
            label=item["label"],
            bbox=(left, top, right - left, bottom - top),
            centroid=(cx * scale_x, cy * scale_y),
            area_pixels=item["area_pixels"],
            mean_probability=item["mean_probability"],
            model_bbox=item["model_bbox"],
            model_centroid=item["model_centroid"],
        ))
    return tuple(scaled)


def _candidate_overlay(original: np.ndarray, mask: np.ndarray, candidates: tuple[StenosisCandidate, ...]) -> np.ndarray:
    base = Image.fromarray(original, mode="L").convert("RGB")
    red_pixels = np.zeros((*mask.shape, 3), dtype=np.uint8)
    red_pixels[mask == 1] = (220, 45, 45)
    red_overlay = Image.fromarray(red_pixels, mode="RGB")
    base = Image.blend(base, red_overlay, alpha=0.42)
    draw = ImageDraw.Draw(base)
    for candidate in candidates:
        x, y, width, height = candidate.bbox
        draw.rectangle((x, y, x + width - 1, y + height - 1), outline=(255, 210, 0), width=2)
        draw.text((x, max(0, y - 14)), f"Predicted candidate {candidate.candidate_id}", fill=(255, 255, 0))
    return np.asarray(base, dtype=np.uint8).copy()


def _combined_visualization(
    original: np.ndarray,
    artery_mask: np.ndarray,
    stenosis_mask: np.ndarray,
    overlay: np.ndarray,
    *,
    max_panel_edge: int = 1024,
) -> np.ndarray:
    height, width = original.shape
    scale = min(1.0, max_panel_edge / max(height, width))
    panel_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    panel_height = panel_size[1] + 30
    canvas = Image.new("RGB", (panel_size[0] * 2, panel_height * 2), (248, 250, 252))
    draw = ImageDraw.Draw(canvas)
    # Model masks are binary {0, 1}; convert foreground to display white before
    # creating a grayscale visualization. Without this, foreground renders near black.
    artery_display = Image.fromarray(np.asarray(artery_mask, dtype=np.uint8) * 255, mode="L").convert("RGB")
    stenosis_display = Image.fromarray(np.asarray(stenosis_mask, dtype=np.uint8) * 255, mode="L").convert("RGB")
    panels = (
        ("Original angiography", Image.fromarray(original, mode="L").convert("RGB")),
        ("Predicted artery mask", artery_display),
        ("Predicted stenosis mask", stenosis_display),
        ("Predicted stenosis candidates", Image.fromarray(overlay, mode="RGB")),
    )
    for index, (title, panel) in enumerate(panels):
        x = (index % 2) * panel_size[0]
        y = (index // 2) * panel_height
        draw.text((x + 8, y + 7), title, fill=(27, 47, 65))
        resized = panel.resize(panel_size, Image.Resampling.NEAREST if "mask" in title else Image.Resampling.BILINEAR)
        canvas.paste(resized, (x, y + 30))
    return np.asarray(canvas, dtype=np.uint8).copy()


class CombinedInferencePipeline:
    """Run both models independently on one unchanged original image."""

    def __init__(
        self,
        *,
        attention_adapter: AttentionUNetAdapter | None = None,
        unetpp_adapter: UNetPPAdapter | None = None,
        stenosis_threshold: float = 0.20,
        minimum_component_area: int = 5,
    ) -> None:
        if not 0.0 <= stenosis_threshold <= 1.0:
            raise ValueError("stenosis_threshold must be between 0 and 1")
        if minimum_component_area < 1:
            raise ValueError("minimum_component_area must be at least 1 pixel")
        self.attention_adapter = attention_adapter or AttentionUNetAdapter(threshold=0.50)
        self.unetpp_adapter = unetpp_adapter or UNetPPAdapter(threshold=stenosis_threshold)
        adapter_threshold = getattr(self.unetpp_adapter, "threshold", stenosis_threshold)
        if abs(float(adapter_threshold) - stenosis_threshold) > 1e-9:
            raise ValueError("stenosis_threshold must match the supplied U-Net++ adapter threshold")
        self.stenosis_threshold = float(stenosis_threshold)
        self.minimum_component_area = minimum_component_area

    def predict(self, image: ImageInput) -> PipelineResult:
        """Predict both masks from the same original input; no mask-to-model chaining."""
        started = perf_counter()
        original = _read_original(image)

        # Preserve the exact input argument: each adapter performs its own model-specific
        # preprocessing from the same original source, never from the other model's mask.
        attention_started = perf_counter()
        artery_result = self.attention_adapter.predict(image)
        attention_seconds = perf_counter() - attention_started

        unetpp_started = perf_counter()
        unetpp_model_input: Any | None = None
        predict_with_input = getattr(self.unetpp_adapter, "predict_with_input", None)
        if callable(predict_with_input):
            stenosis_result, unetpp_model_input = predict_with_input(image)
        else:
            stenosis_result = self.unetpp_adapter.predict(image)
        unetpp_seconds = perf_counter() - unetpp_started

        artery_native = _single_channel(artery_result.mask, "artery mask")
        stenosis_native = _single_channel(stenosis_result.mask, "stenosis mask")
        probabilities_native = _single_channel(stenosis_result.probability_map, "stenosis probability map")
        if not np.isin(artery_native, (0, 1)).all() or not np.isin(stenosis_native, (0, 1)).all():
            raise ValueError("model masks must contain only binary values 0 and 1")
        if probabilities_native.shape != stenosis_native.shape:
            raise ValueError("U-Net++ probability map and mask shapes do not match")
        if not np.isfinite(probabilities_native).all() or np.any((probabilities_native < 0) | (probabilities_native > 1)):
            raise ValueError("U-Net++ probability map must be finite and within [0, 1]")

        height, width = original.shape
        artery_mask = _resize_mask(artery_native, (width, height))
        stenosis_mask = _resize_mask(stenosis_native, (width, height))
        probabilities_aligned = _resize_probabilities(probabilities_native, (width, height))
        raw_candidates = extract_candidates(
            stenosis_native,
            probabilities_native,
            minimum_area=self.minimum_component_area,
        )
        candidates = _scale_candidates(
            raw_candidates,
            model_size=(stenosis_native.shape[1], stenosis_native.shape[0]),
            original_size=(width, height),
        )
        candidate_records = [
            {"candidate_id": item.candidate_id, "label": item.label, "bbox": item.bbox, "centroid": item.centroid}
            for item in candidates
        ]
        source_model_ids, source_thresholds = _measurement_provenance(
            artery_result.metadata,
            stenosis_result.metadata,
            self.stenosis_threshold,
        )
        try:
            percentage_narrowing = estimate_percentage_narrowing(
                artery_mask,
                stenosis_mask,
                candidate_records,
                source_model_ids=source_model_ids,
                source_thresholds=source_thresholds,
            )
        except Exception:
            # Measurement is optional. It must never discard valid model outputs.
            measurement_failure_reason = (
                "artery_and_stenosis_mask_dimensions_mismatch"
                if np.asarray(artery_mask).shape != np.asarray(stenosis_mask).shape
                else "candidate_specific_predicted_mask_geometry_could_not_be_evaluated"
            )
            percentage_narrowing = unavailable_percentage_narrowing(
                candidate_records,
                measurement_failure_reason,
                source_model_ids=source_model_ids,
                source_thresholds=source_thresholds,
            )
        overlay = _candidate_overlay(original, stenosis_mask, candidates)
        gradcam_started = perf_counter()
        gradcam_heatmap: np.ndarray | None = None
        gradcam_reason: str | None = None
        gradcam_metadata: dict[str, Any] = {}
        try:
            gradcam_kwargs: dict[str, Any] = {"prediction_mask": stenosis_result.mask}
            if unetpp_model_input is not None:
                gradcam_kwargs["preprocessed_input"] = unetpp_model_input
            explanation = self.unetpp_adapter.gradcam(image, **gradcam_kwargs)
            candidate_heatmap = np.asarray(explanation.heatmap, dtype=np.float32)
            if candidate_heatmap.shape != (512, 512):
                raise ValueError("Grad-CAM must return a 512x512 heatmap")
            if not np.isfinite(candidate_heatmap).all() or np.any((candidate_heatmap < 0) | (candidate_heatmap > 1)):
                raise ValueError("Grad-CAM heatmap values must be finite and within [0, 1]")
            candidate_metadata = dict(explanation.metadata)
            gradcam_heatmap = np.ascontiguousarray(candidate_heatmap)
            gradcam_metadata = candidate_metadata
        except Exception as exc:
            # Explanations are optional; a failure must not discard valid masks/candidates.
            gradcam_heatmap = None
            gradcam_metadata = {}
            gradcam_reason = f"Grad-CAM could not be generated ({type(exc).__name__}); segmentation results are available."
        gradcam_seconds = perf_counter() - gradcam_started
        combined = _combined_visualization(original, artery_mask, stenosis_mask, overlay)
        total_seconds = perf_counter() - started

        return PipelineResult(
            original_image=original,
            artery_mask=artery_mask,
            stenosis_probability_map=probabilities_aligned,
            stenosis_mask=stenosis_mask,
            candidates=candidates,
            percentage_narrowing=percentage_narrowing,
            candidate_overlay=overlay,
            combined_visualization=combined,
            gradcam_heatmap=gradcam_heatmap,
            model_times={
                "attention_unet_seconds": attention_seconds,
                "unetpp_seconds": unetpp_seconds,
                "gradcam_seconds": gradcam_seconds,
            },
            metadata={
                "attention_unet": artery_result.metadata,
                "unetpp": stenosis_result.metadata,
                "original_size": [width, height],
                "candidate_label": "Predicted stenosis candidates; not confirmed stenoses",
                "candidate_connectivity": 8,
                "minimum_component_area_model_pixels": self.minimum_component_area,
                "candidate_measurement_grid": list(stenosis_native.shape),
                "gradcam_available": gradcam_heatmap is not None,
                "gradcam_target_layer": gradcam_metadata.get("target_layer", GRADCAM_TARGET_LAYER),
                "gradcam_method": gradcam_metadata.get("method", GRADCAM_METHOD),
                "gradcam_target_score": gradcam_metadata.get("target_score"),
                "gradcam_target_score_fallback": gradcam_metadata.get("target_score_fallback"),
                "gradcam_predicted_pixel_count": gradcam_metadata.get("predicted_pixel_count"),
                "gradcam_unavailable_reason": None if gradcam_heatmap is not None else gradcam_reason,
                "clinical_measurements_generated": False,
                "clinical_validation": False,
                "model_times": {
                    "attention_unet_seconds": attention_seconds,
                    "unetpp_seconds": unetpp_seconds,
                    "gradcam_seconds": gradcam_seconds,
                },
                "total_pipeline_seconds": total_seconds,
            },
        )
