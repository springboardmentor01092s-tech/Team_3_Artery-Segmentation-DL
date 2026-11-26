"""Guarded diameter formula for measurements validated outside lesion segmentation.

This helper does not extract a vessel lumen from an image. Callers must supply
calibrated millimetre measurements and explicitly attest to the lumen,
reference-segment, cross-section, and image-location checks.
"""

from __future__ import annotations

import math


def calculate_validated_stenosis_percentage(
    reference_vessel_diameter_mm: float | None,
    minimum_lumen_diameter_mm: float | None,
    *,
    reference_unit: str | None,
    minimum_unit: str | None,
    calibration_verified: bool,
    lumen_boundaries_validated: bool,
    reference_segment_validated: bool,
    cross_sections_perpendicular: bool,
    reference_location_xy: tuple[float, float] | None = None,
    minimum_location_xy: tuple[float, float] | None = None,
    image_shape_hw: tuple[int, int] | None = None,
) -> float | None:
    """Calculate percent narrowing only from fully validated, in-image mm inputs.

    Invalid or missing evidence returns ``None``. Diameters must satisfy
    ``0 < minimum <= reference``; invalid values are rejected, never clipped.
    Locations use pixel ``(x, y)`` coordinates and ``image_shape_hw`` is
    ``(height, width)``. Both locations and the image dimensions are required.
    """
    if not (
        reference_unit == "mm"
        and minimum_unit == "mm"
        and calibration_verified
        and lumen_boundaries_validated
        and reference_segment_validated
        and cross_sections_perpendicular
    ):
        return None
    if reference_vessel_diameter_mm is None or minimum_lumen_diameter_mm is None:
        return None
    try:
        reference = float(reference_vessel_diameter_mm)
        minimum = float(minimum_lumen_diameter_mm)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(reference) or not math.isfinite(minimum):
        return None
    if reference <= 0 or minimum <= 0 or minimum > reference:
        return None
    if image_shape_hw is None or reference_location_xy is None or minimum_location_xy is None:
        return None
    try:
        height, width = image_shape_hw
        height, width = int(height), int(width)
    except (TypeError, ValueError, OverflowError):
        return None
    if height <= 0 or width <= 0:
        return None
    for location in (reference_location_xy, minimum_location_xy):
        try:
            if len(location) != 2:
                return None
            x, y = float(location[0]), float(location[1])
        except (TypeError, ValueError, OverflowError, IndexError):
            return None
        if not math.isfinite(x) or not math.isfinite(y):
            return None
        if not (0 <= x < width and 0 <= y < height):
            return None

    percentage = ((reference - minimum) / reference) * 100.0
    if not math.isfinite(percentage) or not 0 <= percentage <= 100:
        return None
    return percentage
