import numpy as np
import pytest

from app.arcade_ml.lumen_measurement import draw_lumen_measurement, measure_validated_lumen


def vertical_vessel():
    lumen = np.zeros((100, 100), dtype=bool)
    for y in range(10, 90):
        half_width = 5 if not 40 <= y < 60 else 2
        lumen[y, 50 - half_width:50 + half_width] = True
    lesion = np.zeros_like(lumen)
    lesion[42:58, 45:56] = True
    reference = np.zeros_like(lumen)
    reference[15:32, 44:57] = True
    return lumen, lesion, reference


def test_validated_lumen_mask_returns_pixel_only_geometry_without_calibration():
    lumen, lesion, reference = vertical_vessel()
    result = measure_validated_lumen(
        lumen, lesion, reference,
        lumen_boundaries_validated=True, lesion_location_validated=True,
        reference_segment_validated=True,
    )
    assert result["measurement_status"] == "pixel_only_calibration_unavailable"
    assert result["minimum_lumen_diameter_px"] == pytest.approx(4.0, abs=0.5)
    assert result["reference_vessel_diameter_px"] == pytest.approx(10.0, abs=0.5)
    assert result["minimum_location_xy"] is not None
    assert result["reference_location_xy"] is not None
    assert result["centerline_xy"]
    assert result["minimum_lumen_diameter_mm"] is None
    assert result["reference_vessel_diameter_mm"] is None
    assert result["stenosis_percentage"] is None
    assert result["quality"]["clinical_probability"] is None


def test_verified_calibration_uses_cross_section_orientation_and_guarded_formula():
    lumen, lesion, reference = vertical_vessel()
    calibration = {
        "is_dicom": True,
        "pixel_spacing_status": "reported_valid_values",
        "pixel_spacing_row_column_mm": [0.2, 0.2],
        "calibration_verified": True,
        "transform_verified": True,
    }
    result = measure_validated_lumen(
        lumen, lesion, reference,
        lumen_boundaries_validated=True, lesion_location_validated=True,
        reference_segment_validated=True, calibration=calibration,
    )
    assert result["measurement_status"] == "calibrated_research_estimate"
    assert result["minimum_lumen_diameter_mm"] == pytest.approx(0.8, abs=0.15)
    assert result["reference_vessel_diameter_mm"] == pytest.approx(2.0, abs=0.15)
    assert result["stenosis_percentage"] == pytest.approx(60.0, abs=8.0)
    assert result["quality"]["reference_section_count"] >= 3


def test_anisotropic_spacing_uses_row_spacing_for_horizontal_cross_sections():
    lumen = np.zeros((80, 100), dtype=bool)
    lumen[38:42, 10:90] = True
    lesion = np.zeros_like(lumen)
    lesion[35:45, 45:58] = True
    reference = np.zeros_like(lumen)
    reference[30:50, 15:32] = True
    result = measure_validated_lumen(
        lumen, lesion, reference,
        lumen_boundaries_validated=True, lesion_location_validated=True,
        reference_segment_validated=True,
        calibration={"is_dicom": True, "pixel_spacing_status": "reported_valid_values",
                     "pixel_spacing_row_column_mm": [0.5, 0.2],
                     "calibration_verified": True, "transform_verified": True},
    )
    assert result["minimum_lumen_diameter_mm"] == pytest.approx(
        result["minimum_lumen_diameter_px"] * 0.5, abs=0.2,
    )


def test_unverified_pixel_spacing_never_produces_mm_or_percentage():
    lumen, lesion, reference = vertical_vessel()
    result = measure_validated_lumen(
        lumen, lesion, reference,
        lumen_boundaries_validated=True, lesion_location_validated=True,
        reference_segment_validated=True,
        calibration={"is_dicom": True, "pixel_spacing_status": "reported_valid_values",
                     "pixel_spacing_row_column_mm": [0.2, 0.2],
                     "calibration_verified": False, "transform_verified": True},
    )
    assert result["minimum_lumen_diameter_px"] is not None
    assert result["minimum_lumen_diameter_mm"] is None
    assert result["stenosis_percentage"] is None


@pytest.mark.parametrize("flag", ["lumen_boundaries_validated", "lesion_location_validated", "reference_segment_validated"])
def test_unvalidated_boundaries_or_regions_are_rejected(flag):
    lumen, lesion, reference = vertical_vessel()
    flags = {"lumen_boundaries_validated": True, "lesion_location_validated": True,
             "reference_segment_validated": True}
    flags[flag] = False
    result = measure_validated_lumen(lumen, lesion, reference, **flags)
    assert result["measurement_status"] == "unavailable"
    assert result["minimum_lumen_diameter_px"] is None
    assert result["stenosis_percentage"] is None


def test_misaligned_empty_and_overlapping_rois_are_rejected():
    lumen, lesion, reference = vertical_vessel()
    kwargs = dict(lumen_boundaries_validated=True, lesion_location_validated=True,
                  reference_segment_validated=True)
    assert measure_validated_lumen(lumen, lesion[:, :-1], reference, **kwargs)["measurement_status"] == "unavailable"
    assert measure_validated_lumen(lumen, np.zeros_like(lesion), reference, **kwargs)["measurement_status"] == "unavailable"
    assert measure_validated_lumen(lumen, lesion, lesion.copy(), **kwargs)["measurement_status"] == "unavailable"


def test_disconnected_lesion_and_reference_lumen_components_are_rejected():
    lumen, lesion, reference = vertical_vessel()
    lumen[10:20, 5:15] = True
    lesion[12:17, 7:13] = True
    result = measure_validated_lumen(
        lumen, lesion, reference, lumen_boundaries_validated=True,
        lesion_location_validated=True, reference_segment_validated=True,
    )
    assert result["measurement_status"] == "unavailable"
    assert "same single connected" in result["reason"]


def test_overlay_draws_boundaries_centerline_and_measurement_calipers():
    lumen, lesion, reference = vertical_vessel()
    result = measure_validated_lumen(
        lumen, lesion, reference, lumen_boundaries_validated=True,
        lesion_location_validated=True, reference_segment_validated=True,
    )
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    overlay, calipers = draw_lumen_measurement(image, lumen, result)
    assert overlay.shape == image.shape and calipers.shape == image.shape
    assert np.any(overlay != image)
    assert np.any(calipers != image)


def test_non_dicoms_and_invalid_spacing_cannot_become_calibrated():
    lumen, lesion, reference = vertical_vessel()
    for calibration in [
        {"is_dicom": False, "pixel_spacing_status": "reported_valid_values",
         "pixel_spacing_row_column_mm": [0.2, 0.2], "calibration_verified": True, "transform_verified": True},
        {"is_dicom": True, "pixel_spacing_status": "invalid_values",
         "pixel_spacing_row_column_mm": [0.0, 0.2], "calibration_verified": True, "transform_verified": True},
    ]:
        result = measure_validated_lumen(
            lumen, lesion, reference, lumen_boundaries_validated=True,
            lesion_location_validated=True, reference_segment_validated=True,
            calibration=calibration,
        )
        assert result["minimum_lumen_diameter_mm"] is None
        assert result["reference_vessel_diameter_mm"] is None
        assert result["stenosis_percentage"] is None
