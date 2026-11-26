import numpy as np
import cv2

from app.arcade_ml.vessel_width import draw_width_visualizations, measure_vessel_region_widths


def test_horizontal_region_estimates_perpendicular_pixel_widths():
    mask = np.zeros((100, 140), dtype=bool)
    mask[45:54, 10:130] = True
    result = measure_vessel_region_widths(mask)
    assert result["component_count"] == 1
    assert result["width_unit"] == "pixel"
    assert result["semantics"] == "estimated_vessel_region_width_not_lumen_diameter"
    assert len(result["measurements"]) > 0
    assert 7.0 <= result["minimum_width_px"] <= 10.0
    assert all(abs(item["vessel_axis_angle_degrees"]) < 5 for item in result["measurements"])


def test_empty_and_too_small_masks_return_no_fabricated_measurement():
    empty = measure_vessel_region_widths(np.zeros((32, 32), dtype=bool))
    small = np.zeros((32, 32), dtype=bool)
    small[5:7, 5:7] = True
    tiny = measure_vessel_region_widths(small)
    assert empty["measurements"] == [] and empty["minimum_width_px"] is None
    assert tiny["measurements"] == [] and tiny["minimum_width_px"] is None


def test_diagonal_region_uses_local_orientation_for_perpendicular_section():
    mask = np.zeros((100, 100), dtype=np.uint8)
    cv2.line(mask, (10, 10), (90, 90), 1, 9)
    result = measure_vessel_region_widths(mask > 0)
    assert result["measurements"]
    assert all(40 <= item["vessel_axis_angle_degrees"] <= 50 for item in result["measurements"])
    assert all(10 <= item["width_px"] <= 15 for item in result["measurements"])


def test_visualizations_preserve_dimensions_and_draw_sections():
    mask = np.zeros((100, 140), dtype=bool)
    mask[45:54, 10:130] = True
    result = measure_vessel_region_widths(mask)
    image = np.zeros((100, 140, 3), dtype=np.uint8)
    overlay, sections = draw_width_visualizations(image, mask, result)
    assert overlay.shape == sections.shape == image.shape
    assert np.count_nonzero(overlay) > 0
    assert np.count_nonzero(sections) > 0
