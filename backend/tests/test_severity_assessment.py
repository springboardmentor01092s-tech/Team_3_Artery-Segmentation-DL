import json
import math

import pytest

from app.services.severity_assessment import assess_saved_percentage_narrowing


@pytest.mark.parametrize(("value", "expected"), [
    (0, "Normal"),
    (25, "Normal"),
    (25.1, "Mild"),
    (40, "Mild"),
    (49.9, "Mild"),
    (50, "Moderate"),
    (65, "Moderate"),
    (69.9, "Moderate"),
    (70, "Critical"),
    (87.87, "Critical"),
    (100, "Critical"),
])
def test_user_threshold_boundaries(value, expected):
    result = assess_saved_percentage_narrowing(
        {"measurements": [{"candidate_id": 1, "status": "available", "estimated_narrowing_percent": value}]},
        [{"candidate_id": 1}],
    )

    assert result["status"] == "available"
    assert result["measurements"] == [{
        "candidate_id": 1,
        "status": "available",
        "severity": expected,
        "source_narrowing_percent": float(value),
    }]


@pytest.mark.parametrize(("record", "expected_status", "reason"), [
    ({"candidate_id": 1, "status": "available", "estimated_narrowing_percent": None}, "unavailable", "narrowing_value_missing"),
    ({"candidate_id": 1, "status": "available"}, "unavailable", "narrowing_value_missing"),
    ({"candidate_id": 1, "status": "available", "estimated_narrowing_percent": math.nan}, "unavailable", "narrowing_value_is_nan"),
    ({"candidate_id": 1, "status": "available", "estimated_narrowing_percent": math.inf}, "invalid", "narrowing_value_must_be_finite"),
    ({"candidate_id": 1, "status": "available", "estimated_narrowing_percent": -math.inf}, "invalid", "narrowing_value_must_be_finite"),
    ({"candidate_id": 1, "status": "available", "estimated_narrowing_percent": "25"}, "invalid", "narrowing_value_must_be_numeric"),
    ({"candidate_id": 1, "status": "available", "estimated_narrowing_percent": True}, "invalid", "narrowing_value_must_be_numeric"),
    ({"candidate_id": 1, "status": "available", "estimated_narrowing_percent": -0.01}, "invalid", "narrowing_value_out_of_range"),
    ({"candidate_id": 1, "status": "available", "estimated_narrowing_percent": 100.01}, "invalid", "narrowing_value_out_of_range"),
    ({"candidate_id": 1, "status": "unavailable", "estimated_narrowing_percent": 0}, "unavailable", "saved_narrowing_estimate_unavailable"),
])
def test_missing_unavailable_and_invalid_values_are_never_classified(record, expected_status, reason):
    result = assess_saved_percentage_narrowing({"measurements": [record]}, [{"candidate_id": 1}])

    assert result["status"] == "unavailable"
    assert result["measurements"] == [{"candidate_id": 1, "status": expected_status, "reason": reason}]
    assert "severity" not in result["measurements"][0]
    json.dumps(result, allow_nan=False)


def test_missing_narrowing_metadata_and_missing_candidate_record_stay_unavailable():
    missing_object = assess_saved_percentage_narrowing(None, [{"candidate_id": 1}])
    missing_record = assess_saved_percentage_narrowing({"measurements": []}, [{"candidate_id": 2}])

    assert missing_object["measurements"][0]["status"] == "unavailable"
    assert missing_record["measurements"][0]["status"] == "unavailable"
    assert "severity" not in missing_object["measurements"][0]
    assert "severity" not in missing_record["measurements"][0]


def test_non_smaller_predicted_width_diagnostic_does_not_produce_severity():
    result = assess_saved_percentage_narrowing(
        {"measurements": [{
            "candidate_id": 1,
            "status": "unavailable",
            "unavailable_reason": "candidate_predicted_mask_width_not_smaller_than_reference",
        }]},
        [{"candidate_id": 1}],
    )

    assert result["status"] == "unavailable"
    assert result["measurements"] == [{
        "candidate_id": 1,
        "status": "unavailable",
        "reason": "saved_narrowing_estimate_unavailable",
    }]
    assert "severity" not in result["measurements"][0]


def test_candidate_association_is_by_candidate_id_not_list_position():
    result = assess_saved_percentage_narrowing(
        {"measurements": [
            {"candidate_id": 2, "status": "available", "estimated_narrowing_percent": 70},
            {"candidate_id": 1, "status": "available", "estimated_narrowing_percent": 25},
        ]},
        [{"candidate_id": 1}, {"candidate_id": 2}],
    )

    assert [(item["candidate_id"], item["severity"]) for item in result["measurements"]] == [
        (1, "Normal"), (2, "Critical"),
    ]


def test_duplicate_candidate_measurements_are_not_assigned_ambiguously():
    result = assess_saved_percentage_narrowing(
        {"measurements": [
            {"candidate_id": 1, "status": "available", "estimated_narrowing_percent": 0},
            {"candidate_id": 1, "status": "available", "estimated_narrowing_percent": 100},
        ]},
        [{"candidate_id": 1}],
    )

    assert result["measurements"][0]["status"] == "unavailable"
    assert result["measurements"][0]["reason"] == "saved_narrowing_candidate_association_is_ambiguous"
    assert "severity" not in result["measurements"][0]


def test_version_and_threshold_metadata_are_persistable_json():
    result = assess_saved_percentage_narrowing(
        {"measurements": [{"candidate_id": 3, "status": "available", "estimated_narrowing_percent": 25.1}]},
        [{"candidate_id": 3}],
    )

    assert result["algorithm_version"] == "task5-user-specified-thresholds-v1"
    assert result["threshold_source"] == "user_specified_experimental_project_rules"
    assert [item["severity"] for item in result["thresholds"]] == ["Normal", "Mild", "Moderate", "Critical"]
    json.dumps(result, allow_nan=False)
