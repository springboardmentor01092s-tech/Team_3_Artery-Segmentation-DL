import numpy as np
import pytest
import json

from ml.inference.percentage_narrowing import (
    DISCLAIMER,
    REASON_CANDIDATE_WIDTH_NOT_SMALLER_THAN_REFERENCE,
    estimate_percentage_narrowing,
)


def straight_vessel_masks():
    artery = np.zeros((80, 120), dtype=np.uint8)
    for x in range(5, 115):
        if x < 45 or x > 75:
            radius = 5
        elif x <= 60:
            radius = max(2, 5 - 3 * (x - 45) / 15)
        else:
            radius = max(2, 2 + 3 * (x - 60) / 15)
        artery[40 - int(radius):41 + int(radius), x] = 1
    stenosis = np.zeros_like(artery)
    stenosis[artery.astype(bool) & (np.indices(artery.shape)[1] >= 55) & (np.indices(artery.shape)[1] <= 65)] = 1
    candidate = {"candidate_id": 1, "label": "Predicted stenosis candidate 1", "bbox": [55, 34, 11, 13]}
    return artery, stenosis, [candidate]


def horizontal_vessel(height=80, width=120, y=40, start=5, end=115, radius=5):
    artery = np.zeros((height, width), dtype=np.uint8)
    artery[y - radius:y + radius + 1, start:end] = 1
    return artery


def variable_width_vessel(candidate_radius, reference_radius):
    artery = np.zeros((80, 120), dtype=np.uint8)
    for x in range(5, 115):
        radius = candidate_radius if 50 <= x <= 70 else reference_radius
        artery[40 - radius:41 + radius, x] = 1
    stenosis = np.zeros_like(artery)
    stenosis[artery.astype(bool) & (np.indices(artery.shape)[1] >= 55) & (np.indices(artery.shape)[1] <= 65)] = 1
    candidate = {"candidate_id": 1, "label": "Predicted stenosis candidate 1", "bbox": [55, 30, 11, 21]}
    return artery, stenosis, [candidate]


def locally_different_vessel_caliber():
    artery = np.zeros((100, 160), dtype=np.uint8)
    for x in range(5, 155):
        if 60 <= x <= 80:
            radius = 3
        elif 20 <= x < 60 or 81 < x <= 120:
            radius = 6
        else:
            radius = 3
        artery[50 - radius:51 + radius, x] = 1
    stenosis = np.zeros_like(artery)
    stenosis[artery.astype(bool) & (np.indices(artery.shape)[1] >= 65) & (np.indices(artery.shape)[1] <= 75)] = 1
    candidate = {"candidate_id": 1, "label": "Predicted stenosis candidate 1", "bbox": [65, 43, 11, 15]}
    return artery, stenosis, [candidate]


def test_estimates_predicted_mask_widths_and_records_provenance():
    artery, stenosis, candidates = straight_vessel_masks()

    result = estimate_percentage_narrowing(
        artery,
        stenosis,
        candidates,
        source_model_ids={"artery": "attention_unet", "stenosis": "unetpp_resnet34_stenosis"},
        source_thresholds={"artery": 0.50, "stenosis": 0.20},
    )

    measurement = result["measurements"][0]
    assert result["status"] == "available"
    assert result["algorithm_version"] == "candidate-local-reference-predicted-mask-width-v4"
    assert result["coordinate_system"] == "original_image_pixel_grid"
    assert result["measurement_unit"] == "pixel"
    assert result["disclaimer"] == DISCLAIMER
    assert measurement["status"] == "available"
    assert 0 < measurement["minimum_candidate_predicted_mask_width_px"] < measurement["reference_predicted_mask_width_px"]
    assert measurement["estimated_narrowing_percent"] == pytest.approx(
        (measurement["reference_predicted_mask_width_px"] - measurement["minimum_candidate_predicted_mask_width_px"])
        / measurement["reference_predicted_mask_width_px"] * 100,
    )
    assert measurement["quality"]["reference_centerline_samples"] >= 5
    assert measurement["quality"]["lesion_dilation_pixels"] == 5
    assert measurement["diagnostics"]["estimator_version"] == result["algorithm_version"]
    assert measurement["diagnostics"]["calculated_percentage"] == pytest.approx(
        measurement["estimated_narrowing_percent"]
    )
    assert result["diagnostic_summary"]["valid_estimate_count"] == 1


def test_candidate_width_smaller_than_reference_keeps_existing_estimate_unchanged():
    artery, stenosis, candidates = variable_width_vessel(candidate_radius=2, reference_radius=5)

    result = estimate_percentage_narrowing(artery, stenosis, candidates)
    measurement = result["measurements"][0]

    assert result["status"] == "available"
    assert measurement["status"] == "available"
    assert measurement["minimum_candidate_predicted_mask_width_px"] == pytest.approx(6.0)
    assert measurement["reference_predicted_mask_width_px"] == pytest.approx(12.0)
    assert measurement["estimated_narrowing_percent"] == pytest.approx(50.0)


@pytest.mark.parametrize("candidate_radius", [5, 7], ids=["equal-width", "greater-width"])
def test_candidate_width_equal_to_or_greater_than_reference_is_unavailable(candidate_radius):
    artery, stenosis, candidates = variable_width_vessel(candidate_radius=candidate_radius, reference_radius=5)

    result = estimate_percentage_narrowing(artery, stenosis, candidates)
    measurement = result["measurements"][0]

    assert result["status"] == "unavailable"
    assert result["unavailable_reason"] == "No candidate had a predicted-mask width smaller than its reference artery-mask width."
    assert measurement["status"] == "unavailable"
    assert measurement["unavailable_reason"] == REASON_CANDIDATE_WIDTH_NOT_SMALLER_THAN_REFERENCE
    assert "estimated_narrowing_percent" not in measurement
    assert "minimum_candidate_predicted_mask_width_px" not in measurement
    assert "reference_predicted_mask_width_px" not in measurement


def test_local_reference_does_not_use_distant_narrower_segments_and_supports_about_45_percent():
    artery, stenosis, candidates = locally_different_vessel_caliber()

    result = estimate_percentage_narrowing(artery, stenosis, candidates)
    measurement = result["measurements"][0]

    assert result["status"] == "available"
    assert measurement["minimum_candidate_predicted_mask_width_px"] == pytest.approx(8.0)
    assert measurement["reference_predicted_mask_width_px"] == pytest.approx(14.0)
    assert measurement["estimated_narrowing_percent"] == pytest.approx(45.0, abs=3.0)
    assert measurement["quality"]["reference_centerline_samples_per_side"] == [16, 16]
    assert measurement["quality"]["reference_width_per_side_px"] == [14.0, 14.0]
    diagnostics = measurement["diagnostics"]
    assert diagnostics["candidate_id"] == 1
    assert diagnostics["associated_artery_component_id"] is not None
    assert diagnostics["candidate_width_px"] == pytest.approx(8.0)
    assert diagnostics["reference_side_1_median_width_px"] == pytest.approx(14.0)
    assert diagnostics["reference_side_2_median_width_px"] == pytest.approx(14.0)
    assert diagnostics["reference_side_1_sample_count"] == diagnostics["reference_side_2_sample_count"] == 16
    assert diagnostics["reference_width_px"] == pytest.approx(14.0)
    assert diagnostics["calculated_percentage"] == pytest.approx(measurement["estimated_narrowing_percent"])


@pytest.mark.parametrize("curve_amplitude", [0, 3, 6, 10])
def test_smooth_curved_vessel_with_digital_skeleton_spur_remains_measurable(curve_amplitude):
    artery = np.zeros((120, 180), dtype=np.uint8)
    stenosis = np.zeros_like(artery)
    for x in range(8, 172):
        center_y = 55 + round(curve_amplitude * np.sin(x / 20))
        radius = 3 if 70 <= x <= 90 else 6
        artery[center_y - radius:center_y + radius + 1, x] = 1
        if 77 <= x <= 83:
            stenosis[center_y - 2:center_y + 3, x] = 1
    candidate = {"candidate_id": 1, "bbox": [77, 40, 7, 20]}

    result = estimate_percentage_narrowing(artery, stenosis, [candidate])
    measurement = result["measurements"][0]

    assert measurement["status"] == "available"
    assert measurement["diagnostics"]["reference_side_1_sample_count"] >= 5
    assert measurement["diagnostics"]["reference_side_2_sample_count"] >= 5
    if curve_amplitude >= 6:
        assert sum(measurement["diagnostics"]["branch_continuations_per_side"]) > 0
        assert result["diagnostic_summary"]["straight_branch_continuation_count"] == sum(
            measurement["diagnostics"]["branch_continuations_per_side"]
        )


def test_estimate_fails_closed_for_invalid_shapes_or_out_of_grid_candidate():
    artery, stenosis, candidates = straight_vessel_masks()
    with pytest.raises(ValueError, match="identical aligned dimensions"):
        estimate_percentage_narrowing(artery, stenosis[:, :-1], candidates)

    candidates[0]["bbox"] = [110, 79, 20, 2]
    result = estimate_percentage_narrowing(artery, stenosis, candidates)
    assert result["status"] == "unavailable"
    assert result["measurements"][0]["status"] == "unavailable"
    assert "bbox" in result["measurements"][0]["unavailable_reason"]


def test_multiple_candidates_cannot_reuse_one_stenosis_component():
    artery, stenosis, candidates = straight_vessel_masks()
    candidates.append({"candidate_id": 2, "label": "Predicted stenosis candidate 2", "bbox": [55, 35, 11, 12]})

    result = estimate_percentage_narrowing(artery, stenosis, candidates)

    assert result["status"] == "unavailable"
    assert all(item["status"] == "unavailable" for item in result["measurements"])
    assert all("same_persisted" in item["unavailable_reason"] for item in result["measurements"])


def test_centroid_resolves_candidate_bbox_that_intersects_multiple_components():
    artery = horizontal_vessel()
    stenosis = np.zeros_like(artery)
    stenosis[35:46, 30:35] = 1
    stenosis[35:46, 80:85] = 1
    candidate = {"candidate_id": 1, "bbox": [25, 30, 65, 21], "centroid": [82.0, 40.0]}

    result = estimate_percentage_narrowing(artery, stenosis, [candidate])

    assert result["measurements"][0]["status"] == "unavailable"
    assert result["measurements"][0]["candidate_id"] == 1
    assert result["measurements"][0]["unavailable_reason"] == REASON_CANDIDATE_WIDTH_NOT_SMALLER_THAN_REFERENCE


def test_multiple_components_without_resolving_candidate_centroid_stay_unavailable():
    artery = horizontal_vessel()
    stenosis = np.zeros_like(artery)
    stenosis[35:46, 30:35] = 1
    stenosis[35:46, 80:85] = 1
    candidate = {"candidate_id": 1, "bbox": [25, 30, 65, 21], "centroid": [55.0, 40.0]}

    result = estimate_percentage_narrowing(artery, stenosis, [candidate])

    assert result["measurements"][0]["status"] == "unavailable"
    assert result["measurements"][0]["unavailable_reason"] == "candidate_centroid_does_not_identify_one_stenosis_component"


def test_empty_masks_no_overlap_and_low_overlap_return_unavailable():
    empty = np.zeros((40, 60), dtype=np.uint8)
    candidate = {"candidate_id": 1, "bbox": [25, 18, 5, 5]}
    assert estimate_percentage_narrowing(empty, empty, [candidate])["measurements"][0]["status"] == "unavailable"

    artery_without_stenosis = horizontal_vessel(height=40, width=60, y=20, start=5, end=55)
    missing_stenosis = estimate_percentage_narrowing(artery_without_stenosis, empty, [candidate])
    assert missing_stenosis["measurements"][0]["status"] == "unavailable"
    assert missing_stenosis["measurements"][0]["unavailable_reason"] == (
        "candidate_bbox_contains_no_persisted_stenosis_pixels"
    )
    assert missing_stenosis["diagnostic_summary"]["missing_or_mismatched_mask_count"] == 1

    stenosis = empty.copy()
    stenosis[18:23, 25:30] = 1
    assert estimate_percentage_narrowing(empty, stenosis, [candidate])["measurements"][0]["unavailable_reason"] == "candidate_has_no_artery_overlap"

    artery = empty.copy()
    artery[20, 25] = 1
    low = estimate_percentage_narrowing(artery, stenosis, [candidate])
    assert low["measurements"][0]["unavailable_reason"] == "candidate_artery_overlap_is_too_low"


def test_ambiguous_overlap_between_multiple_artery_components_is_rejected():
    artery = np.zeros((80, 100), dtype=np.uint8)
    artery[20, 45:51] = 1
    artery[22, 45:50] = 1
    stenosis = np.zeros_like(artery)
    stenosis[20, 45:51] = 1
    stenosis[21, 45] = 1
    stenosis[22, 45:50] = 1  # Connects the mask across two distinct artery components.
    candidate = {"candidate_id": 1, "bbox": [45, 20, 6, 3]}

    result = estimate_percentage_narrowing(artery, stenosis, [candidate])

    assert result["measurements"][0]["status"] == "unavailable"
    assert "multiple_artery_components" in result["measurements"][0]["unavailable_reason"]


def test_distinct_stenosis_components_are_measured_separately():
    artery = horizontal_vessel()
    stenosis = np.zeros_like(artery)
    stenosis[35:46, 30:35] = 1
    stenosis[35:46, 80:85] = 1
    candidates = [
        {"candidate_id": 1, "bbox": [30, 35, 5, 11]},
        {"candidate_id": 2, "bbox": [80, 35, 5, 11]},
    ]

    result = estimate_percentage_narrowing(artery, stenosis, candidates)

    assert [item["candidate_id"] for item in result["measurements"]] == [1, 2]
    assert all(item["status"] == "unavailable" for item in result["measurements"])
    assert all(
        item["unavailable_reason"] == REASON_CANDIDATE_WIDTH_NOT_SMALLER_THAN_REFERENCE
        for item in result["measurements"]
    )


def test_branching_artery_with_ambiguous_local_reference_stays_unavailable():
    artery = horizontal_vessel()
    artery[20:41, 60] = 1
    stenosis = np.zeros_like(artery)
    stenosis[35:46, 55:66] = 1
    candidate = {"candidate_id": 1, "bbox": [55, 35, 11, 11]}

    result = estimate_percentage_narrowing(artery, stenosis, [candidate])

    assert result["measurements"][0]["status"] == "unavailable"
    assert "reference" in result["measurements"][0]["unavailable_reason"]
    assert result["diagnostic_summary"]["branch_or_endpoint_rejection_count"] == 1


def test_insufficient_or_asymmetric_local_reference_stays_unavailable():
    artery = np.zeros((40, 60), dtype=np.uint8)
    artery[15:26, 10:40] = 1
    stenosis = np.zeros_like(artery)
    stenosis[18:23, 20:25] = 1
    candidate = {"candidate_id": 1, "bbox": [20, 18, 5, 5]}
    short_result = estimate_percentage_narrowing(artery, stenosis, [candidate])
    assert short_result["measurements"][0]["status"] == "unavailable"
    assert short_result["measurements"][0]["unavailable_reason"] == (
        "insufficient_local_reference_centerline_samples"
    )
    assert short_result["diagnostic_summary"]["insufficient_reference_sample_count"] == 1
    assert short_result["diagnostic_summary"]["branch_or_endpoint_rejection_count"] == 1

    asymmetric = np.zeros((80, 140), dtype=np.uint8)
    for x in range(5, 135):
        if x < 50:
            radius = 3
        elif x < 58:
            radius = max(2, 3 - (x - 50) // 4)
        elif x < 62:
            radius = 2
        else:
            radius = min(14, 2 + (x - 62) * 3)
        asymmetric[40 - radius:41 + radius, x] = 1
    lesion = np.zeros_like(asymmetric)
    lesion[asymmetric.astype(bool) & (np.indices(asymmetric.shape)[1] >= 58) & (np.indices(asymmetric.shape)[1] <= 61)] = 1
    asymmetric_result = estimate_percentage_narrowing(
        asymmetric, lesion, [{"candidate_id": 1, "bbox": [58, 30, 4, 21]}]
    )
    assert asymmetric_result["measurements"][0]["status"] == "unavailable"
    assert asymmetric_result["measurements"][0]["unavailable_reason"] == "local_reference_widths_disagree"


def test_all_returned_metadata_is_json_safe_and_non_finite_masks_are_rejected():
    artery, stenosis, candidates = straight_vessel_masks()
    result = estimate_percentage_narrowing(artery, stenosis, candidates)
    json.dumps(result, allow_nan=False)
    with pytest.raises(ValueError, match="binary"):
        estimate_percentage_narrowing(artery.astype(np.float32) * np.nan, stenosis, candidates)
