"""Conservative experimental widths from predicted binary segmentation masks.

Measurements are on the original image pixel grid. They are not lumen
diameters, calibrated physical measurements, or clinically validated results.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy import ndimage
from skimage.morphology import skeletonize


ALGORITHM_VERSION = "candidate-local-reference-predicted-mask-width-v4"
DISCLAIMER = "Experimental predicted-mask-based narrowing estimate — not a clinically calibrated lumen measurement."
MIN_CANDIDATE_OVERLAP_FRACTION = 0.50
MIN_COMPONENT_DOMINANCE = 0.80
MIN_LOCAL_REFERENCE_SIDE_SAMPLES = 5
LESION_DILATION_PIXELS = 5
MAX_LOCAL_REFERENCE_WINDOW_PIXELS = 40.0
LOCAL_REFERENCE_SIDE_AGREEMENT = 0.35
STRAIGHT_THROUGH_MIN_COSINE = math.cos(math.radians(45.0))
STRAIGHT_THROUGH_MIN_SCORE_GAP = 0.25
REASON_CANDIDATE_WIDTH_NOT_SMALLER_THAN_REFERENCE = "candidate_predicted_mask_width_not_smaller_than_reference"
_EIGHT_CONNECTED = np.ones((3, 3), dtype=np.uint8)


def _candidate_diagnostics(candidate_id: int) -> dict[str, Any]:
    return {
        "estimator_version": ALGORITHM_VERSION,
        "candidate_id": candidate_id,
        "associated_artery_component_id": None,
        "candidate_width_px": None,
        "candidate_centerline_sample_count": 0,
        "candidate_overlap_fraction": None,
        "artery_component_dominance": None,
        "reference_side_1_median_width_px": None,
        "reference_side_2_median_width_px": None,
        "reference_side_1_sample_count": 0,
        "reference_side_2_sample_count": 0,
        "branch_continuations_per_side": [0, 0],
        "sampling_stop_reasons": [],
        "reference_width_px": None,
        "reference_window_pixels": None,
        "calculated_percentage": None,
        "sampling_rejection_reason": None,
    }


def _unavailable_measurement(
    candidate_id: int,
    reason: str,
    label: str | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "candidate_id": candidate_id,
        "status": "unavailable",
        "unavailable_reason": reason,
    }
    diagnostic_record = diagnostics if diagnostics is not None else _candidate_diagnostics(candidate_id)
    diagnostic_record["sampling_rejection_reason"] = reason
    item["diagnostics"] = diagnostic_record
    if label:
        item["label"] = label
    return item


def _diagnostic_summary(measurements: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    reason_counts: Counter[str] = Counter()
    insufficient = inconsistent = branch_endpoint = missing_masks = available = 0
    straight_branch_continuations = 0
    for item in measurements:
        diagnostics = item.get("diagnostics")
        if isinstance(diagnostics, Mapping):
            branches = diagnostics.get("branch_continuations_per_side", [])
            if isinstance(branches, Sequence) and not isinstance(branches, (str, bytes)):
                straight_branch_continuations += sum(
                    value for value in branches
                    if isinstance(value, int) and not isinstance(value, bool) and value >= 0
                )
        if item.get("status") == "available":
            available += 1
            continue
        reason = str(item.get("unavailable_reason", "unknown"))
        reason_counts[reason] += 1
        stops = diagnostics.get("sampling_stop_reasons", []) if isinstance(diagnostics, Mapping) else []
        if reason == "insufficient_local_reference_centerline_samples":
            insufficient += 1
        if reason == "local_reference_widths_disagree":
            inconsistent += 1
        if any(stop in {"branch", "endpoint", "branch_or_endpoint"} for stop in stops):
            branch_endpoint += 1
        if reason in {
            "candidate_stenosis_component_is_missing",
            "candidate_bbox_contains_no_persisted_stenosis_pixels",
            "candidate_has_no_artery_overlap",
            "candidate_artery_overlap_is_too_low",
            "candidate_overlaps_multiple_artery_components_ambiguously",
            "artery_and_stenosis_mask_dimensions_mismatch",
        }:
            missing_masks += 1
    unavailable = len(measurements) - available
    categorized_reasons = {
        "insufficient_local_reference_centerline_samples",
        "local_reference_widths_disagree",
        "candidate_centerline_reference_sides_are_ambiguous",
        "candidate_stenosis_component_is_missing",
        "candidate_bbox_contains_no_persisted_stenosis_pixels",
        "candidate_has_no_artery_overlap",
        "candidate_artery_overlap_is_too_low",
        "candidate_overlaps_multiple_artery_components_ambiguously",
        "artery_and_stenosis_mask_dimensions_mismatch",
    }
    other = sum(count for reason, count in reason_counts.items() if reason not in categorized_reasons)
    return {
        "candidate_count": len(measurements),
        "counts_may_overlap": True,
        "straight_branch_continuation_count": straight_branch_continuations,
        "valid_estimate_count": available,
        "unavailable_count": unavailable,
        "insufficient_reference_sample_count": insufficient,
        "inconsistent_reference_width_count": inconsistent,
        "branch_or_endpoint_rejection_count": branch_endpoint,
        "missing_or_mismatched_mask_count": missing_masks,
        "other_failure_count": other,
        "failure_reason_counts": dict(sorted(reason_counts.items())),
    }


def unavailable_percentage_narrowing(
    candidates: Sequence[Mapping[str, Any]] | None,
    reason: str,
    *,
    source_model_ids: Mapping[str, str] | None = None,
    source_thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Build a JSON-safe unavailable result when a stage cannot be evaluated."""
    candidate_items = []
    for index, candidate in enumerate(candidates or (), start=1):
        candidate_id = candidate.get("candidate_id", index)
        if isinstance(candidate_id, bool) or not isinstance(candidate_id, int) or candidate_id < 1:
            candidate_id = index
        candidate_items.append(_unavailable_measurement(candidate_id, reason, candidate.get("label")))
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "status": "unavailable",
        "coordinate_system": "original_image_pixel_grid",
        "measurement_unit": "pixel",
        "disclaimer": DISCLAIMER,
        "measurements": candidate_items,
        "diagnostic_summary": _diagnostic_summary(candidate_items),
        "unavailable_reason": reason,
        "limitations": [
            "Widths describe thresholded predicted-mask foreground, not a confirmed lumen boundary.",
            "No physical pixel spacing or clinical calibration is available.",
        ],
        "source_model_ids": dict(source_model_ids or {}),
        "source_thresholds": dict(source_thresholds or {}),
        "quality_parameters": {
            "minimum_candidate_overlap_fraction": MIN_CANDIDATE_OVERLAP_FRACTION,
            "minimum_artery_component_dominance": MIN_COMPONENT_DOMINANCE,
            "minimum_local_reference_centerline_samples_per_side": MIN_LOCAL_REFERENCE_SIDE_SAMPLES,
            "maximum_local_reference_window_pixels": MAX_LOCAL_REFERENCE_WINDOW_PIXELS,
            "maximum_reference_side_disagreement_fraction": LOCAL_REFERENCE_SIDE_AGREEMENT,
            "straight_through_max_angle_degrees": 45.0,
            "straight_through_min_cosine_score_gap": STRAIGHT_THROUGH_MIN_SCORE_GAP,
            "lesion_region_dilation_pixels": LESION_DILATION_PIXELS,
        },
    }


def _binary_mask(value: np.ndarray, name: str) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim != 2 or not array.size:
        raise ValueError(f"{name} must be a non-empty 2D mask")
    if not np.isfinite(array).all() or not np.isin(array, (0, 1, 255)).all():
        raise ValueError(f"{name} must be binary (0/1 or persisted PNG 0/255)")
    return array != 0


def _candidate_bbox(candidate: Mapping[str, Any], width: int, height: int) -> tuple[int, int, int, int]:
    candidate_id = candidate.get("candidate_id")
    if isinstance(candidate_id, bool) or not isinstance(candidate_id, int) or candidate_id < 1:
        raise ValueError("candidate_id must be a positive integer")
    bbox = candidate.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        raise ValueError("candidate bbox must be [x, y, width, height] in original-image coordinates")
    if any(isinstance(value, bool) or not isinstance(value, (int, np.integer)) for value in bbox):
        raise ValueError("candidate bbox values must be integers")
    x, y, box_width, box_height = map(int, bbox)
    if box_width <= 0 or box_height <= 0 or x < 0 or y < 0 or x + box_width > width or y + box_height > height:
        raise ValueError("candidate bbox is outside the original-image grid")
    return x, y, box_width, box_height


def _skeleton_neighbors(skeleton: np.ndarray, point: tuple[int, int]) -> list[tuple[int, int]]:
    """Get 8-neighbors while suppressing redundant diagonal corner connections."""
    y, x = point
    height, width = skeleton.shape
    neighbors: list[tuple[int, int]] = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if not (0 <= ny < height and 0 <= nx < width) or not skeleton[ny, nx]:
                continue
            if dy != 0 and dx != 0 and (skeleton[y, nx] or skeleton[ny, x]):
                continue
            neighbors.append((ny, nx))
    return neighbors


def _clear_straight_continuation(
    current: tuple[int, int],
    previous: tuple[int, int],
    candidates: list[tuple[int, int]],
) -> tuple[int, int] | None:
    """Resolve a digital skeleton spur only when one path continues unambiguously."""
    incoming = np.asarray((current[0] - previous[0], current[1] - previous[1]), dtype=np.float64)
    incoming_norm = float(np.linalg.norm(incoming))
    if incoming_norm == 0 or not candidates:
        return None
    incoming /= incoming_norm
    scores: list[tuple[float, tuple[int, int]]] = []
    for point in candidates:
        outgoing = np.asarray((point[0] - current[0], point[1] - current[1]), dtype=np.float64)
        norm = float(np.linalg.norm(outgoing))
        if norm > 0:
            scores.append((float(np.dot(incoming, outgoing / norm)), point))
    scores.sort(reverse=True, key=lambda item: item[0])
    if not scores or scores[0][0] < STRAIGHT_THROUGH_MIN_COSINE:
        return None
    if len(scores) > 1 and scores[0][0] - scores[1][0] < STRAIGHT_THROUGH_MIN_SCORE_GAP:
        return None
    return scores[0][1]


def _trace_local_reference_side(
    *,
    skeleton: np.ndarray,
    distance_map: np.ndarray,
    candidate_region: np.ndarray,
    other_lesion_region: np.ndarray,
    inside_point: tuple[int, int],
    outside_point: tuple[int, int],
    window_pixels: float,
) -> tuple[list[float], str, int]:
    """Sample one side, crossing only branches with a unique straight continuation."""
    previous = inside_point
    current = outside_point
    traveled = 0.0
    visited = {inside_point}
    widths: list[float] = []
    branch_continuations = 0
    while traveled < window_pixels and current not in visited:
        y, x = current
        if candidate_region[y, x] or other_lesion_region[y, x]:
            return widths, "candidate_or_neighbour_boundary", branch_continuations
        neighbors = _skeleton_neighbors(skeleton, current)
        if len(neighbors) > 2:
            forward = [point for point in neighbors if point != previous]
            continuation = _clear_straight_continuation(current, previous, forward)
            if continuation is None:
                return widths, "branch", branch_continuations
            # Thin digital skeletons can have a short side spur at a curved
            # raster transition. Cross only an unambiguous straight-through node
            # and skip its width because junction geometry inflates the EDT radius.
            branch_continuations += 1
            step = math.sqrt(2.0) if continuation[0] != y and continuation[1] != x else 1.0
            traveled += step
            visited.add(current)
            previous, current = current, continuation
            continue
        if len(neighbors) != 2:
            return widths, "endpoint", branch_continuations
        width = float(distance_map[y, x] * 2.0)
        if not math.isfinite(width) or width <= 0:
            return widths, "invalid_width", branch_continuations
        widths.append(width)
        next_points = [point for point in neighbors if point != previous]
        if len(next_points) != 1:
            return widths, "branch_or_endpoint", branch_continuations
        following = next_points[0]
        step = math.sqrt(2.0) if following[0] != y and following[1] != x else 1.0
        traveled += step
        visited.add(current)
        previous, current = current, following
    return widths, "window_limit" if traveled >= window_pixels else "centerline_cycle", branch_continuations


def _measure_candidate(
    candidate: Mapping[str, Any],
    *,
    artery: np.ndarray,
    candidate_stenosis: np.ndarray,
    other_stenosis: np.ndarray,
    artery_labels: np.ndarray,
) -> dict[str, Any]:
    candidate_id = int(candidate["candidate_id"])
    label = candidate.get("label") if isinstance(candidate.get("label"), str) else None
    diagnostics = _candidate_diagnostics(candidate_id)
    height, width = artery.shape
    x, y, box_width, box_height = _candidate_bbox(candidate, width, height)
    candidate_mask = candidate_stenosis
    if candidate_mask.shape != artery.shape or not candidate_mask.any():
        return _unavailable_measurement(candidate_id, "candidate_stenosis_component_is_missing", label, diagnostics)
    candidate_area = int(candidate_mask.sum())

    overlap_by_artery = np.bincount(artery_labels[candidate_mask], minlength=int(artery_labels.max()) + 1)
    overlap_by_artery[0] = 0
    if candidate_area == 0 or overlap_by_artery.sum() == 0:
        return _unavailable_measurement(candidate_id, "candidate_has_no_artery_overlap", label, diagnostics)
    selected_label = int(np.argmax(overlap_by_artery))
    best_overlap = int(overlap_by_artery[selected_label])
    overlap_fraction = best_overlap / candidate_area
    dominance = best_overlap / int(overlap_by_artery.sum())
    diagnostics["associated_artery_component_id"] = selected_label
    diagnostics["candidate_overlap_fraction"] = overlap_fraction
    diagnostics["artery_component_dominance"] = dominance
    if overlap_fraction < MIN_CANDIDATE_OVERLAP_FRACTION:
        return _unavailable_measurement(candidate_id, "candidate_artery_overlap_is_too_low", label, diagnostics)
    if dominance < MIN_COMPONENT_DOMINANCE:
        return _unavailable_measurement(candidate_id, "candidate_overlaps_multiple_artery_components_ambiguously", label, diagnostics)

    artery_component = artery_labels == selected_label
    skeleton = skeletonize(artery_component)
    distance_map = ndimage.distance_transform_edt(artery_component)
    lesion_region = ndimage.binary_dilation(candidate_mask, iterations=LESION_DILATION_PIXELS)
    lesion_centerline = skeleton & lesion_region
    lesion_widths = distance_map[lesion_centerline] * 2.0
    if not len(lesion_widths) or not np.isfinite(lesion_widths).all() or np.any(lesion_widths <= 0):
        return _unavailable_measurement(candidate_id, "candidate_width_is_zero_or_non_finite", label, diagnostics)
    minimum_candidate_width = float(np.min(lesion_widths))
    diagnostics["candidate_width_px"] = minimum_candidate_width
    diagnostics["candidate_centerline_sample_count"] = int(len(lesion_widths))

    # Use nearby centerline samples on both sides. A whole-component median can
    # be dominated by distant branches or vessel segments with another caliber.
    median_candidate_width = float(np.median(lesion_widths))
    reference_window = min(
        MAX_LOCAL_REFERENCE_WINDOW_PIXELS,
        max(5.0, 2.0 * median_candidate_width),
    )
    diagnostics["reference_window_pixels"] = reference_window
    lesion_points = [tuple(int(value) for value in point) for point in np.argwhere(lesion_centerline)]
    boundary_edges = {
        (inside, outside)
        for inside in lesion_points
        for outside in _skeleton_neighbors(skeleton, inside)
        if not lesion_region[outside]
    }
    if len(boundary_edges) != 2:
        stop_reason = "branch" if len(boundary_edges) > 2 else "endpoint" if len(boundary_edges) == 1 else "centerline_topology_ambiguous"
        diagnostics["sampling_stop_reasons"] = [stop_reason]
        return _unavailable_measurement(candidate_id, "candidate_centerline_reference_sides_are_ambiguous", label, diagnostics)

    other_lesion_region = ndimage.binary_dilation(other_stenosis, iterations=LESION_DILATION_PIXELS)
    traced_sides = [
        _trace_local_reference_side(
            skeleton=skeleton,
            distance_map=distance_map,
            candidate_region=lesion_region,
            other_lesion_region=other_lesion_region,
            inside_point=inside,
            outside_point=outside,
            window_pixels=reference_window,
        )
        for inside, outside in sorted(boundary_edges)
    ]
    side_samples = [samples for samples, _stop_reason, _branches in traced_sides]
    diagnostics["reference_side_1_sample_count"] = len(side_samples[0])
    diagnostics["reference_side_2_sample_count"] = len(side_samples[1])
    diagnostics["sampling_stop_reasons"] = [stop_reason for _samples, stop_reason, _branches in traced_sides]
    diagnostics["branch_continuations_per_side"] = [branches for _samples, _reason, branches in traced_sides]
    diagnostics["reference_side_1_median_width_px"] = (
        float(np.median(side_samples[0])) if side_samples[0] else None
    )
    diagnostics["reference_side_2_median_width_px"] = (
        float(np.median(side_samples[1])) if side_samples[1] else None
    )
    if any(len(samples) < MIN_LOCAL_REFERENCE_SIDE_SAMPLES for samples in side_samples):
        return _unavailable_measurement(candidate_id, "insufficient_local_reference_centerline_samples", label, diagnostics)
    side_medians = [float(np.median(samples)) for samples in side_samples]
    if not all(math.isfinite(value) and value > 0 for value in side_medians):
        return _unavailable_measurement(candidate_id, "reference_width_is_zero_or_non_finite", label, diagnostics)
    side_agreement = abs(side_medians[0] - side_medians[1]) / max(side_medians)
    if side_agreement > LOCAL_REFERENCE_SIDE_AGREEMENT:
        return _unavailable_measurement(candidate_id, "local_reference_widths_disagree", label, diagnostics)

    reference_widths = np.asarray([width for samples in side_samples for width in samples], dtype=np.float64)
    reference_width = float(np.median(reference_widths))
    if not math.isfinite(reference_width) or reference_width <= 0:
        return _unavailable_measurement(candidate_id, "reference_width_is_zero_or_non_finite", label, diagnostics)
    diagnostics["reference_width_px"] = reference_width
    if minimum_candidate_width >= reference_width:
        return _unavailable_measurement(
            candidate_id,
            REASON_CANDIDATE_WIDTH_NOT_SMALLER_THAN_REFERENCE,
            label,
            diagnostics,
        )

    narrowing = ((reference_width - minimum_candidate_width) / reference_width) * 100.0
    if not math.isfinite(narrowing) or narrowing < 0 or narrowing > 100:
        return _unavailable_measurement(candidate_id, "percentage_is_outside_the_valid_formula_range", label, diagnostics)
    diagnostics["calculated_percentage"] = narrowing
    diagnostics["sampling_rejection_reason"] = None

    item: dict[str, Any] = {
        "candidate_id": candidate_id,
        "status": "available",
        "reference_predicted_mask_width_px": reference_width,
        "minimum_candidate_predicted_mask_width_px": minimum_candidate_width,
        "estimated_narrowing_percent": narrowing,
        "diagnostics": diagnostics,
        "association": "candidate-specific stenosis component and its largest-overlap artery component",
        "quality": {
            "candidate_overlap_fraction": overlap_fraction,
            "artery_component_dominance": dominance,
            "candidate_centerline_samples": int(len(lesion_widths)),
            "reference_centerline_samples": int(len(reference_widths)),
            "reference_centerline_samples_per_side": [len(samples) for samples in side_samples],
            "reference_width_per_side_px": side_medians,
            "reference_side_agreement_fraction": side_agreement,
            "reference_window_pixels": reference_window,
            "straight_through_max_angle_degrees": 45.0,
            "straight_through_min_cosine_score_gap": STRAIGHT_THROUGH_MIN_SCORE_GAP,
            "lesion_dilation_pixels": LESION_DILATION_PIXELS,
        },
    }
    if label:
        item["label"] = label
    return item


def estimate_percentage_narrowing(
    artery_mask: np.ndarray,
    stenosis_mask: np.ndarray,
    candidates: Sequence[Mapping[str, Any]],
    *,
    source_model_ids: Mapping[str, str] | None = None,
    source_thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Estimate candidate-specific predicted-mask widths without claiming lumen size.

    Inputs must already be aligned to the same original-image pixel grid. The
    function never resizes masks and returns per-candidate unavailability rather
    than clipping invalid geometry to a plausible value. It samples candidate widths
    inside a five-pixel dilation and estimates reference width from bounded adjacent
    paths on both sides of the same artery centerline. A uniquely straight continuation
    can cross a digital branch spur; ambiguous branches, endpoints and other lesion
    regions stop sampling. Candidate diagnostics and aggregate reason counts are saved
    in the result metadata. Insufficient or asymmetric local references are rejected.
    """
    artery = _binary_mask(artery_mask, "artery_mask")
    stenosis = _binary_mask(stenosis_mask, "stenosis_mask")
    if artery.shape != stenosis.shape:
        raise ValueError("artery_mask and stenosis_mask must have identical aligned dimensions")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise ValueError("candidates must be a sequence of candidate records")
    if any(not isinstance(candidate, Mapping) for candidate in candidates):
        raise ValueError("each candidate must be a mapping")

    candidate_ids = [candidate.get("candidate_id") for candidate in candidates]
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in candidate_ids):
        raise ValueError("candidate IDs must be positive integers")
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("candidate IDs must be unique")
    if not candidates:
        return unavailable_percentage_narrowing(
            (), "No predicted stenosis candidates were returned.",
            source_model_ids=source_model_ids, source_thresholds=source_thresholds,
        )

    artery_labels, _ = ndimage.label(artery, structure=_EIGHT_CONNECTED)
    stenosis_labels, _ = ndimage.label(stenosis, structure=_EIGHT_CONNECTED)
    candidate_labels: dict[int, int] = {}
    label_errors: dict[int, str] = {}
    height, width = artery.shape
    for candidate in candidates:
        candidate_id = int(candidate["candidate_id"])
        try:
            x, y, box_width, box_height = _candidate_bbox(candidate, width, height)
        except ValueError:
            label_errors[candidate_id] = "candidate_bbox_is_invalid_or_outside_original_image"
            continue
        labels_in_box = np.unique(stenosis_labels[y:y + box_height, x:x + box_width])
        labels_in_box = labels_in_box[labels_in_box > 0]
        if len(labels_in_box) == 0:
            label_errors[candidate_id] = "candidate_bbox_contains_no_persisted_stenosis_pixels"
            continue
        if len(labels_in_box) == 1:
            candidate_labels[candidate_id] = int(labels_in_box[0])
            continue
        centroid = candidate.get("centroid")
        if not isinstance(centroid, (list, tuple)) or len(centroid) != 2:
            label_errors[candidate_id] = "candidate_bbox_intersects_multiple_stenosis_components"
            continue
        try:
            cx, cy = (float(value) for value in centroid)
        except (TypeError, ValueError):
            label_errors[candidate_id] = "candidate_bbox_intersects_multiple_stenosis_components"
            continue
        if not math.isfinite(cx) or not math.isfinite(cy) or not (x <= cx < x + box_width and y <= cy < y + box_height):
            label_errors[candidate_id] = "candidate_centroid_is_invalid_or_outside_bbox"
            continue
        center_label = int(stenosis_labels[min(height - 1, int(round(cy))), min(width - 1, int(round(cx)))])
        if center_label not in labels_in_box:
            label_errors[candidate_id] = "candidate_centroid_does_not_identify_one_stenosis_component"
            continue
        candidate_labels[candidate_id] = center_label

    label_owners: dict[int, list[int]] = {}
    for candidate_id, label_id in candidate_labels.items():
        label_owners.setdefault(label_id, []).append(candidate_id)
    shared_candidate_ids = {
        candidate_id
        for owners in label_owners.values() if len(owners) > 1
        for candidate_id in owners
    }
    results: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = int(candidate["candidate_id"])
        if candidate_id in label_errors:
            results.append(_unavailable_measurement(candidate_id, label_errors[candidate_id], candidate.get("label")))
            continue
        if candidate_id in shared_candidate_ids:
            results.append(_unavailable_measurement(candidate_id, "multiple_candidates_map_to_the_same_persisted_stenosis_component", candidate.get("label")))
            continue
        try:
            results.append(_measure_candidate(
                candidate,
                artery=artery,
                candidate_stenosis=stenosis_labels == candidate_labels[candidate_id],
                other_stenosis=(stenosis_labels > 0) & (stenosis_labels != candidate_labels[candidate_id]),
                artery_labels=artery_labels,
            ))
        except (IndexError, KeyError, TypeError, ValueError):
            # A malformed individual candidate must not prevent other candidates
            # or the two segmentation outputs from being returned.
            results.append(_unavailable_measurement(candidate_id, "candidate_geometry_could_not_be_evaluated", candidate.get("label")))

    available_count = sum(item["status"] == "available" for item in results)
    status = "unavailable" if available_count == 0 else "available" if available_count == len(results) else "partial"
    all_widths_not_smaller = bool(results) and all(
        item.get("unavailable_reason") == REASON_CANDIDATE_WIDTH_NOT_SMALLER_THAN_REFERENCE
        for item in results
    )
    reason = None if status == "available" else (
        "No candidate had a predicted-mask width smaller than its reference artery-mask width."
        if status == "unavailable" and all_widths_not_smaller
        else "No candidate had sufficient associated mask geometry." if status == "unavailable"
        else "One or more candidate measurements were unavailable because geometry was ambiguous or insufficient."
    )
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "status": status,
        "coordinate_system": "original_image_pixel_grid",
        "measurement_unit": "pixel",
        "disclaimer": DISCLAIMER,
        "measurements": results,
        "diagnostic_summary": _diagnostic_summary(results),
        "unavailable_reason": reason,
        "limitations": [
            "Widths describe thresholded predicted-mask foreground, not a confirmed lumen boundary.",
            "No physical pixel spacing or clinical calibration is available.",
            "The stenosis threshold is provisional; candidate and artery masks are model predictions.",
        ],
        "source_model_ids": dict(source_model_ids or {}),
        "source_thresholds": dict(source_thresholds or {}),
        "quality_parameters": {
            "minimum_candidate_overlap_fraction": MIN_CANDIDATE_OVERLAP_FRACTION,
            "minimum_artery_component_dominance": MIN_COMPONENT_DOMINANCE,
            "minimum_local_reference_centerline_samples_per_side": MIN_LOCAL_REFERENCE_SIDE_SAMPLES,
            "maximum_local_reference_window_pixels": MAX_LOCAL_REFERENCE_WINDOW_PIXELS,
            "maximum_reference_side_disagreement_fraction": LOCAL_REFERENCE_SIDE_AGREEMENT,
            "straight_through_max_angle_degrees": 45.0,
            "straight_through_min_cosine_score_gap": STRAIGHT_THROUGH_MIN_SCORE_GAP,
            "lesion_region_dilation_pixels": LESION_DILATION_PIXELS,
        },
    }
