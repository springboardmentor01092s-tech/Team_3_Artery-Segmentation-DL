"""Geometry for explicitly validated lumen masks; not an image lumen segmenter.

ARCADE lesion polygons and SYNTAX region masks are not valid inputs. Callers
must supply expert-validated lumen boundaries plus lesion/reference ROIs. The
routine deliberately reports pixel-only diameters unless the caller also
provides verified image-plane calibration and transform provenance.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from .diameter_measurement import calculate_validated_stenosis_percentage


def _morphological_skeleton(mask: np.ndarray) -> np.ndarray:
    current = mask.astype(np.uint8) * 255
    skeleton = np.zeros_like(current)
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    while cv2.countNonZero(current):
        eroded = cv2.erode(current, kernel)
        opened = cv2.dilate(eroded, kernel)
        skeleton = cv2.bitwise_or(skeleton, cv2.subtract(current, opened))
        current = eroded
    return skeleton > 0


def _local_axis(points_yx: np.ndarray, x: int, y: int, radius: int) -> tuple[np.ndarray, float] | None:
    nearby = points_yx[(np.abs(points_yx[:, 0] - y) <= radius) & (np.abs(points_yx[:, 1] - x) <= radius)]
    if len(nearby) < 5:
        return None
    xy = nearby[:, ::-1].astype(np.float64)
    covariance = np.cov(xy, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    if not np.isfinite(eigenvalues).all() or eigenvalues[-1] <= 1e-8:
        return None
    linearity = float(eigenvalues[-1] / max(float(eigenvalues[-2]), 1e-8))
    if linearity < 1.6:
        return None
    axis = eigenvectors[:, -1]
    axis /= max(float(np.linalg.norm(axis)), 1e-12)
    return axis, linearity


def _measure_section(mask: np.ndarray, x: int, y: int, normal_xy: np.ndarray) -> dict | None:
    offsets = np.arange(-100.0, 100.0001, 0.25)
    xs = np.rint(x + normal_xy[0] * offsets).astype(int)
    ys = np.rint(y + normal_xy[1] * offsets).astype(int)
    h, w = mask.shape
    valid = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
    samples = np.zeros(len(offsets), dtype=bool)
    samples[valid] = mask[ys[valid], xs[valid]]
    center = int(np.argmin(np.abs(offsets)))
    if not samples[center]:
        return None
    left = right = center
    while left > 0 and samples[left - 1]:
        left -= 1
    while right + 1 < len(samples) and samples[right + 1]:
        right += 1
    if left == 0 or right == len(samples) - 1:
        return None
    width_px = float(offsets[right] - offsets[left])
    if not math.isfinite(width_px) or width_px <= 0:
        return None
    return {
        "x": int(x), "y": int(y), "width_px": round(width_px, 3),
        "normal_x": float(normal_xy[0]), "normal_y": float(normal_xy[1]),
        "start_xy": [float(x + normal_xy[0] * offsets[left]), float(y + normal_xy[1] * offsets[left])],
        "end_xy": [float(x + normal_xy[0] * offsets[right]), float(y + normal_xy[1] * offsets[right])],
    }


def _width_mm(width_px: float, normal_x: float, normal_y: float, calibration: dict) -> float | None:
    if not (
        calibration.get("is_dicom") is True
        and calibration.get("calibration_verified") is True
        and calibration.get("transform_verified") is True
        and calibration.get("pixel_spacing_status") == "reported_valid_values"
    ):
        return None
    try:
        row_spacing, column_spacing = (float(value) for value in calibration["pixel_spacing_row_column_mm"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not (math.isfinite(row_spacing) and math.isfinite(column_spacing) and row_spacing > 0 and column_spacing > 0):
        return None
    # Convert a vector in image (x=column,y=row) coordinates into patient-plane
    # physical distance. This assumes the supplied verified calibration applies
    # to the current, unresampled image plane.
    value = width_px * math.hypot(normal_x * column_spacing, normal_y * row_spacing)
    return value if math.isfinite(value) and value > 0 else None


def measure_validated_lumen(
    lumen_mask: np.ndarray,
    lesion_roi: np.ndarray,
    reference_roi: np.ndarray,
    *,
    lumen_boundaries_validated: bool,
    lesion_location_validated: bool,
    reference_segment_validated: bool,
    calibration: dict | None = None,
    axis_radius_px: int = 8,
    min_reference_sections: int = 3,
) -> dict:
    """Measure MLD/reference diameter from a supplied expert-validated mask.

    This is a geometry utility, not a segmenter. The lesion and reference ROIs
    are explicit inputs and must identify the same connected lumen component.
    A calibrated percent narrowing is returned only if all geometry and
    physical-calibration checks are affirmed. A numeric quality probability is
    intentionally not emitted.
    """
    unavailable = {
        "measurement_status": "unavailable",
        "minimum_lumen_diameter_px": None,
        "reference_vessel_diameter_px": None,
        "minimum_lumen_diameter_mm": None,
        "reference_vessel_diameter_mm": None,
        "stenosis_percentage": None,
        "minimum_location_xy": None,
        "reference_location_xy": None,
        "centerline_xy": [],
        "cross_sections": [],
        "quality": "unavailable",
        "quality_notes": [],
        "reason": None,
        "semantics": "requires expert-validated inner-lumen mask and lesion/reference ROIs",
    }
    if not (lumen_boundaries_validated and lesion_location_validated and reference_segment_validated):
        unavailable["reason"] = "Expert validation is required for lumen boundaries, lesion location, and the reference segment."
        return unavailable
    masks = [np.asarray(value, dtype=bool) for value in (lumen_mask, lesion_roi, reference_roi)]
    if any(mask.ndim != 2 for mask in masks) or len({mask.shape for mask in masks}) != 1:
        unavailable["reason"] = "Lumen and lesion/reference masks must be aligned 2D arrays of identical dimensions."
        return unavailable
    lumen, lesion, reference = masks
    if not lumen.any() or not lesion.any() or not reference.any():
        unavailable["reason"] = "The validated lumen, lesion ROI, and reference ROI must each contain foreground pixels."
        return unavailable
    if np.any(lesion & reference):
        unavailable["reason"] = "Lesion and healthy reference ROIs must not overlap."
        return unavailable
    _, labels, _, _ = cv2.connectedComponentsWithStats(lumen.astype(np.uint8), connectivity=8)
    lesion_components = set(np.unique(labels[lesion]).tolist()) - {0}
    reference_components = set(np.unique(labels[reference]).tolist()) - {0}
    if len(lesion_components) != 1 or lesion_components != reference_components:
        unavailable["reason"] = "Lesion and reference ROIs must lie on the same single connected lumen component."
        return unavailable
    component_id = int(next(iter(lesion_components)))
    if int(axis_radius_px) < 2 or int(min_reference_sections) < 1:
        unavailable["reason"] = "Centerline window and reference section requirements are invalid."
        return unavailable

    component = labels == component_id
    skeleton = _morphological_skeleton(component)
    points_yx = np.argwhere(skeleton)
    if len(points_yx) < 7:
        unavailable["reason"] = "The validated lumen mask is too short to estimate a stable centerline."
        return unavailable
    lesion_sections: list[dict] = []
    reference_sections: list[dict] = []
    centerline_xy = []
    distance = cv2.distanceTransform(component.astype(np.uint8), cv2.DIST_L2, 5)
    for y_raw, x_raw in points_yx:
        x, y = int(x_raw), int(y_raw)
        if distance[y, x] < 1.0:
            continue
        axis_info = _local_axis(points_yx, x, y, int(axis_radius_px))
        if axis_info is None:
            continue
        axis, linearity = axis_info
        normal = np.asarray([-axis[1], axis[0]], dtype=np.float64)
        section = _measure_section(component, x, y, normal)
        if section is None:
            continue
        section["local_linearity"] = round(linearity, 3)
        section["diameter_mm"] = _width_mm(section["width_px"], float(normal[0]), float(normal[1]), calibration or {})
        centerline_xy.append([x, y])
        if lesion[y, x]:
            lesion_sections.append(section)
        if reference[y, x]:
            reference_sections.append(section)
    if not lesion_sections or len(reference_sections) < int(min_reference_sections):
        unavailable["reason"] = (
            f"Insufficient valid perpendicular sections: lesion={len(lesion_sections)}, "
            f"reference={len(reference_sections)}, required reference={int(min_reference_sections)}."
        )
        return unavailable

    calibrated_sections = all(section["diameter_mm"] is not None for section in lesion_sections + reference_sections)
    minimum = min(lesion_sections, key=lambda item: item["diameter_mm"] if calibrated_sections else item["width_px"])
    reference_px = float(np.median([section["width_px"] for section in reference_sections]))
    reference_median_mm_values = [section["diameter_mm"] for section in reference_sections if section["diameter_mm"] is not None]
    reference_mm = float(np.median(reference_median_mm_values)) if len(reference_median_mm_values) >= int(min_reference_sections) else None
    minimum_mm = minimum["diameter_mm"]
    reference_selector_value = reference_mm if calibrated_sections and reference_mm is not None else reference_px
    reference_location_section = min(reference_sections, key=lambda item: abs(
        (item["diameter_mm"] if calibrated_sections else item["width_px"]) - reference_selector_value
    ))
    height, width = lumen.shape
    percentage = calculate_validated_stenosis_percentage(
        reference_mm, minimum_mm,
        reference_unit="mm" if reference_mm is not None else None,
        minimum_unit="mm" if minimum_mm is not None else None,
        calibration_verified=bool((calibration or {}).get("calibration_verified") and (calibration or {}).get("transform_verified")),
        lumen_boundaries_validated=lumen_boundaries_validated,
        reference_segment_validated=reference_segment_validated,
        cross_sections_perpendicular=True,
        reference_location_xy=(float(reference_location_section["x"]), float(reference_location_section["y"])),
        minimum_location_xy=(float(minimum["x"]), float(minimum["y"])),
        image_shape_hw=(height, width),
    )
    calibration_valid = reference_mm is not None and minimum_mm is not None
    ref_values = np.asarray([section["width_px"] for section in reference_sections], dtype=np.float64)
    coefficient_of_variation = float(ref_values.std() / ref_values.mean()) if ref_values.mean() > 0 else math.inf
    notes = [
        "Measurements are calculated from an externally supplied, explicitly validated lumen mask and validated ROIs; this project does not currently produce such masks.",
        "The reference diameter is the median of perpendicular widths inside the expert-selected reference ROI.",
        "Quality values describe geometric consistency only and are not clinical confidence or probabilities.",
    ]
    if not calibration_valid:
        notes.append("Physical calibration or image-transform provenance is absent/unverified; diameters and narrowing are pixel-only.")
    if calibration_valid and percentage is None:
        notes.append("Calibrated diameters were obtained, but the supplied values do not support a valid stenosis ratio under the guarded rules.")
    if calibration_valid and reference_mm is not None and minimum_mm is not None and minimum_mm > reference_mm:
        reason = "Stenosis percentage unavailable: minimum diameter exceeds the supplied reference diameter."
    elif percentage is None:
        reason = "Stenosis percentage unavailable: verified calibrated millimetre measurements are required in addition to validated lumen geometry."
    else:
        reason = None
    return {
        "measurement_status": (
            "calibrated_research_estimate" if percentage is not None
            else "calibrated_diameters_stenosis_unavailable" if calibration_valid
            else "pixel_only_calibration_unavailable"
        ),
        "minimum_lumen_diameter_px": round(float(minimum["width_px"]), 3),
        "reference_vessel_diameter_px": round(reference_px, 3),
        "minimum_lumen_diameter_mm": round(float(minimum_mm), 4) if minimum_mm is not None else None,
        "reference_vessel_diameter_mm": round(float(reference_mm), 4) if reference_mm is not None else None,
        "stenosis_percentage": round(float(percentage), 3) if percentage is not None else None,
        "minimum_location_xy": [minimum["x"], minimum["y"]],
        "reference_location_xy": [reference_location_section["x"], reference_location_section["y"]],
        "centerline_xy": centerline_xy,
        "cross_sections": lesion_sections + reference_sections,
        "quality": {
            "reference_section_count": len(reference_sections),
            "lesion_section_count": len(lesion_sections),
            "reference_width_coefficient_of_variation": round(coefficient_of_variation, 4) if math.isfinite(coefficient_of_variation) else None,
            "reference_geometry": "stable" if coefficient_of_variation <= 0.25 else "variable_review_required",
            "clinical_probability": None,
        },
        "quality_notes": notes,
        "reason": reason,
        "semantics": "expert_validated_lumen_geometry_only",
    }


def draw_lumen_measurement(image_bgr: np.ndarray, lumen_mask: np.ndarray, result: dict) -> tuple[np.ndarray, np.ndarray]:
    """Draw validated lumen contour, centerline, and minimum/reference calipers."""
    image = np.asarray(image_bgr)
    mask = np.asarray(lumen_mask, dtype=bool)
    if image.ndim != 3 or image.shape[:2] != mask.shape:
        raise ValueError("Image and lumen mask dimensions must align.")
    overlay = image.copy()
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(overlay, contours, -1, (0, 220, 255), 1, cv2.LINE_AA)
    calipers = overlay.copy()
    for x, y in result.get("centerline_xy", []):
        cv2.circle(overlay, (int(x), int(y)), 1, (0, 255, 0), -1)
    locations = [
        (result.get("minimum_location_xy"), (0, 0, 255), "MIN"),
        (result.get("reference_location_xy"), (255, 160, 0), "REF"),
    ]
    sections_by_key = {(item["x"], item["y"]): item for item in result.get("cross_sections", [])}
    for location, color, label in locations:
        if not location:
            continue
        x, y = int(location[0]), int(location[1])
        section = sections_by_key.get((x, y))
        if not section:
            continue
        start = tuple(int(round(value)) for value in section["start_xy"])
        end = tuple(int(round(value)) for value in section["end_xy"])
        cv2.line(calipers, start, end, color, 2, cv2.LINE_AA)
        cv2.circle(calipers, (x, y), 3, color, -1)
        cv2.putText(calipers, f"{label} {section['width_px']:.2f}px", (x + 4, y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
    return overlay, calipers
