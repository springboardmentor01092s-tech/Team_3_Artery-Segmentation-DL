import pytest
import numpy as np

from app.arcade_ml import inference
from app.arcade_ml.diameter_measurement import calculate_validated_stenosis_percentage
from app.arcade_ml.inference import StenosisAnalyzer


VALID = {
    "reference_unit": "mm",
    "minimum_unit": "mm",
    "calibration_verified": True,
    "lumen_boundaries_validated": True,
    "reference_segment_validated": True,
    "cross_sections_perpendicular": True,
    "reference_location_xy": (10, 10),
    "minimum_location_xy": (20, 10),
    "image_shape_hw": (64, 64),
}


@pytest.mark.parametrize(
    ("reference", "minimum", "expected"),
    [(4.0, 2.0, 50.0), (4.0, 4.0, 0.0), (4.0, 3.0, 25.0), (5.0, 1.0, 80.0)],
)
def test_calculates_percentage_from_validated_mm_diameters(reference, minimum, expected):
    assert calculate_validated_stenosis_percentage(reference, minimum, **VALID) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("reference", "minimum"),
    [(None, 2.0), (0.0, 1.0), (-1.0, 1.0), (4.0, 0.0), (4.0, -1.0), (4.0, 5.0), (float("nan"), 1.0), (float("inf"), 1.0)],
)
def test_rejects_missing_zero_invalid_or_out_of_range_diameters(reference, minimum):
    assert calculate_validated_stenosis_percentage(reference, minimum, **VALID) is None


@pytest.mark.parametrize(
    "evidence",
    [
        {"calibration_verified": False},
        {"lumen_boundaries_validated": False},
        {"reference_segment_validated": False},
        {"cross_sections_perpendicular": False},
    ],
)
def test_rejects_missing_calibration_or_invalid_lumen_geometry(evidence):
    assert calculate_validated_stenosis_percentage(4.0, 2.0, **(VALID | evidence)) is None


@pytest.mark.parametrize(
    "units",
    [{"reference_unit": None}, {"minimum_unit": "px"}, {"reference_unit": "cm", "minimum_unit": "cm"}],
)
def test_rejects_missing_or_non_millimetre_units(units):
    assert calculate_validated_stenosis_percentage(4.0, 2.0, **(VALID | units)) is None


@pytest.mark.parametrize(
    "geometry",
    [
        {"reference_location_xy": None},
        {"minimum_location_xy": (-1, 10)},
        {"reference_location_xy": (64, 10)},
        {"image_shape_hw": (0, 64)},
    ],
)
def test_rejects_missing_or_out_of_image_measurement_locations(geometry):
    assert calculate_validated_stenosis_percentage(4.0, 2.0, **(VALID | geometry)) is None


def test_current_lesion_mask_inference_never_treats_candidate_boxes_as_diameters(monkeypatch):
    analyzer = StenosisAnalyzer.__new__(StenosisAnalyzer)
    analyzer.model = object()
    analyzer.meta = {"normalization": "none"}
    analyzer.image_size = 16
    analyzer.device = "cpu"
    analyzer.threshold = 0.5
    analyzer.info = lambda: {"architecture": "test-lesson-mask"}

    probability = np.zeros((32, 32), dtype=np.float32)
    probability[8:18, 9:20] = 0.9
    monkeypatch.setattr(inference, "predict_image", lambda *_args, **_kwargs: probability)
    result = analyzer.analyze(np.zeros((32, 32, 3), dtype=np.uint8), min_area=1)

    assert result["n_candidates"] == 1
    assert result["candidates"][0]["width"] == 11
    assert result["diameter_measurement"]["measurement_status"] == "unavailable"
    assert result["diameter_measurement"]["reference_vessel_diameter_mm"] is None
    assert result["diameter_measurement"]["minimum_lumen_diameter_mm"] is None
    assert result["percentage_narrowing"] is None
