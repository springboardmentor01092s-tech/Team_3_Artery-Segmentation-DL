"""Experimental pixel widths from SYNTAX vessel-region masks.

These are not lumen diameters. The SYNTAX labels describe named coronary
segments and are not calibrated, validated inner-lumen contours.
"""

from __future__ import annotations

import cv2
import numpy as np


def _skeletonize(mask: np.ndarray) -> np.ndarray:
    current = (mask.astype(np.uint8) * 255)
    skeleton = np.zeros_like(current)
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    while cv2.countNonZero(current):
        eroded = cv2.erode(current, kernel)
        opened = cv2.dilate(eroded, kernel)
        skeleton = cv2.bitwise_or(skeleton, cv2.subtract(current, opened))
        current = eroded
    return skeleton > 0


def _orientation(points_yx: np.ndarray, x: int, y: int, radius: int = 8) -> tuple[np.ndarray, float] | None:
    nearby = points_yx[
        (np.abs(points_yx[:, 0] - y) <= radius)
        & (np.abs(points_yx[:, 1] - x) <= radius)
    ]
    if len(nearby) < 5:
        return None
    xy = nearby[:, ::-1].astype(np.float32)
    covariance = np.cov(xy, rowvar=False)
    values, vectors = np.linalg.eigh(covariance)
    if not np.isfinite(values).all() or values[-1] < 1e-6:
        return None
    linearity = float(values[-1] / max(values[-2], 1e-6))
    if linearity < 1.6:  # reject branch junctions and ambiguous local direction
        return None
    direction = vectors[:, -1]
    direction /= max(float(np.linalg.norm(direction)), 1e-8)
    return direction, linearity


def _cross_section_width(mask: np.ndarray, x: int, y: int, normal: np.ndarray) -> float | None:
    height, width = mask.shape
    offsets = np.arange(-50.0, 50.01, 0.5)
    xs = np.rint(x + normal[0] * offsets).astype(int)
    ys = np.rint(y + normal[1] * offsets).astype(int)
    inside_image = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
    samples = np.zeros(len(offsets), dtype=bool)
    samples[inside_image] = mask[ys[inside_image], xs[inside_image]]
    center = int(np.argmin(np.abs(offsets)))
    if not samples[center]:
        return None
    left = center
    right = center
    while left > 0 and samples[left - 1]:
        left -= 1
    while right + 1 < len(samples) and samples[right + 1]:
        right += 1
    if left == 0 or right == len(samples) - 1:
        return None
    measured = float((right - left + 1) * 0.5)
    return measured if 1.5 <= measured <= 60.0 else None


def measure_vessel_region_widths(
    binary_mask: np.ndarray,
    *,
    min_component_area: int = 30,
    max_measurements: int = 24,
) -> dict:
    """Return quality-filtered, pixel-only region widths at local normals.

    PCA over nearby skeleton pixels estimates local vessel-axis orientation;
    width is sampled along the perpendicular line. Branch points, short or
    low-quality components, invalid widths, and edge-clipped sections are
    omitted. The result is explicitly not lumen-caliper ground truth.
    """
    if binary_mask.ndim != 2 or min_component_area < 1 or max_measurements < 1:
        return {"component_count": 0, "measurements": [], "minimum_width_px": None,
                "width_unit": "pixel", "semantics": "estimated_vessel_region_width_not_lumen_diameter"}
    mask = np.asarray(binary_mask, dtype=bool)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    component_count = 0
    found: list[dict] = []
    all_skeleton = np.zeros(mask.shape, dtype=bool)
    for component_id in range(1, count):
        area = int(stats[component_id, cv2.CC_STAT_AREA])
        if area < min_component_area:
            continue
        component = labels == component_id
        skeleton = _skeletonize(component)
        points = np.argwhere(skeleton)
        if len(points) < 7:
            continue
        component_count += 1
        all_skeleton |= skeleton
        distance = cv2.distanceTransform(component.astype(np.uint8), cv2.DIST_L2, 5)
        previous: tuple[int, int] | None = None
        for y, x in points[::3]:
            y, x = int(y), int(x)
            if distance[y, x] < 1.5:
                continue
            if previous and (x - previous[0]) ** 2 + (y - previous[1]) ** 2 < 36:
                continue
            local = _orientation(points, x, y)
            if local is None:
                continue
            axis, linearity = local
            normal = np.asarray([-axis[1], axis[0]], dtype=np.float32)
            width_px = _cross_section_width(component, x, y, normal)
            if width_px is None:
                continue
            previous = (x, y)
            angle = float(np.degrees(np.arctan2(axis[1], axis[0])))
            found.append({"x": x, "y": y, "width_px": round(width_px, 2),
                          "vessel_axis_angle_degrees": round(angle, 1),
                          "local_linearity": round(linearity, 2), "quality": "estimated"})

    # Keep spatially distinct narrow observations rather than repeated adjacent
    # samples around one point; none is treated as a lesion or lumen minimum.
    selected: list[dict] = []
    for item in sorted(found, key=lambda row: row["width_px"]):
        if all((item["x"] - other["x"]) ** 2 + (item["y"] - other["y"]) ** 2 >= 64
               for other in selected):
            selected.append(item)
        if len(selected) >= max_measurements:
            break
    selected.sort(key=lambda row: (row["y"], row["x"]))
    widths = [row["width_px"] for row in selected]
    return {
        "component_count": component_count,
        "measurements": selected,
        "minimum_width_px": min(widths) if widths else None,
        "width_unit": "pixel",
        "semantics": "estimated_vessel_region_width_not_lumen_diameter",
        "quality_notes": [
            "Widths use a locally estimated centerline normal and are pixel-only.",
            "Branch junctions, ambiguous orientation, and edge-clipped slices are excluded.",
            "SYNTAX segment-region masks are not validated lumen boundaries.",
        ],
        "centerline_mask": all_skeleton,
    }


def draw_width_visualizations(image_bgr: np.ndarray, mask: np.ndarray, result: dict) -> tuple[np.ndarray, np.ndarray]:
    """Render vessel mask/centerline and estimated perpendicular sections."""
    base = image_bgr.copy()
    overlay = base.copy()
    overlay[np.asarray(mask, dtype=bool)] = (overlay[np.asarray(mask, dtype=bool)] * 0.55
                                               + np.array([255, 100, 0]) * 0.45).astype(np.uint8)
    centerlines = result.get("centerline_mask")
    if centerlines is not None:
        overlay[centerlines] = (0, 255, 80)
    sections = base.copy()
    if centerlines is not None:
        sections[centerlines] = (0, 180, 60)
    for index, item in enumerate(result["measurements"], start=1):
        angle = np.radians(item["vessel_axis_angle_degrees"] + 90.0)
        half = min(30.0, item["width_px"] / 2.0 + 3.0)
        dx, dy = int(round(np.cos(angle) * half)), int(round(np.sin(angle) * half))
        point = (int(item["x"]), int(item["y"]))
        cv2.line(sections, (point[0] - dx, point[1] - dy), (point[0] + dx, point[1] + dy), (0, 0, 255), 1)
        cv2.circle(sections, point, 2, (0, 255, 255), -1)
        cv2.putText(sections, f"{index}:{item['width_px']:.1f}px", (point[0] + 2, point[1] - 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1, cv2.LINE_AA)
    return overlay, sections
