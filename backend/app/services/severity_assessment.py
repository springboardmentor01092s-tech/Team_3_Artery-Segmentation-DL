"""Task 5 experimental severity labels from saved Task 6 narrowing estimates."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping
from typing import Any


ALGORITHM_VERSION = "task5-user-specified-thresholds-v1"
THRESHOLDS = [
    {"severity": "Normal", "minimum": 0.0, "maximum": 25.0, "minimum_inclusive": True, "maximum_inclusive": True},
    {"severity": "Mild", "minimum": 25.0, "maximum": 50.0, "minimum_inclusive": False, "maximum_inclusive": False},
    {"severity": "Moderate", "minimum": 50.0, "maximum": 70.0, "minimum_inclusive": True, "maximum_inclusive": False},
    {"severity": "Critical", "minimum": 70.0, "maximum": 100.0, "minimum_inclusive": True, "maximum_inclusive": True},
]
_SEVERITY_LABELS = {entry["severity"] for entry in THRESHOLDS}


def _candidate_id(item: Mapping[str, Any]) -> int | None:
    value = item.get("candidate_id")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def _unavailable(candidate_id: int, reason: str) -> dict[str, Any]:
    return {"candidate_id": candidate_id, "status": "unavailable", "reason": reason}


def _invalid(candidate_id: int, reason: str) -> dict[str, Any]:
    return {"candidate_id": candidate_id, "status": "invalid", "reason": reason}


def _classify_value(candidate_id: int, value: object) -> dict[str, Any]:
    if value is None:
        return _unavailable(candidate_id, "narrowing_value_missing")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return _invalid(candidate_id, "narrowing_value_must_be_numeric")
    if math.isnan(value):
        return _unavailable(candidate_id, "narrowing_value_is_nan")
    if not math.isfinite(value):
        return _invalid(candidate_id, "narrowing_value_must_be_finite")
    if value < 0 or value > 100:
        return _invalid(candidate_id, "narrowing_value_out_of_range")

    if value <= 25:
        severity = "Normal"
    elif value < 50:
        severity = "Mild"
    elif value < 70:
        severity = "Moderate"
    else:
        severity = "Critical"
    if severity not in _SEVERITY_LABELS:  # Defensive against accidental rule edits.
        return _invalid(candidate_id, "severity_threshold_configuration_invalid")
    return {
        "candidate_id": candidate_id,
        "status": "available",
        "severity": severity,
        "source_narrowing_percent": float(value),
    }


def assess_saved_percentage_narrowing(
    percentage_narrowing: object,
    candidates: object,
) -> dict[str, Any]:
    """Classify each candidate from its saved narrowing value, without recalculating it."""
    if not isinstance(candidates, list) or any(not isinstance(item, Mapping) for item in candidates):
        return _summary([], "candidate_metadata_invalid")
    candidate_ids = [_candidate_id(item) for item in candidates]
    if any(candidate_id is None for candidate_id in candidate_ids) or len(set(candidate_ids)) != len(candidate_ids):
        return _summary([], "candidate_ids_invalid_or_duplicated")

    records = percentage_narrowing.get("measurements") if isinstance(percentage_narrowing, Mapping) else None
    if not isinstance(records, list):
        records = []
    records_by_id: dict[int, list[Mapping[str, Any]]] = {}
    for record in records:
        if isinstance(record, Mapping):
            candidate_id = _candidate_id(record)
            if candidate_id is not None:
                records_by_id.setdefault(candidate_id, []).append(record)

    results: list[dict[str, Any]] = []
    for candidate_id in candidate_ids:
        assert candidate_id is not None
        associated = records_by_id.get(candidate_id, [])
        if not associated:
            results.append(_unavailable(candidate_id, "saved_narrowing_estimate_not_found_for_candidate"))
            continue
        if len(associated) != 1:
            results.append(_unavailable(candidate_id, "saved_narrowing_candidate_association_is_ambiguous"))
            continue
        record = associated[0]
        if record.get("status") != "available":
            results.append(_unavailable(candidate_id, "saved_narrowing_estimate_unavailable"))
            continue
        results.append(_classify_value(candidate_id, record.get("estimated_narrowing_percent")))

    return _summary(results)


def _summary(measurements: list[dict[str, Any]], empty_reason: str | None = None) -> dict[str, Any]:
    available_count = sum(item["status"] == "available" for item in measurements)
    status = "unavailable" if available_count == 0 else "available" if available_count == len(measurements) else "partial"
    invalid_count = sum(item["status"] == "invalid" for item in measurements)
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "threshold_source": "user_specified_experimental_project_rules",
        "status": status,
        "thresholds": THRESHOLDS,
        "measurements": measurements,
        "unavailable_reason": empty_reason or (
            "No candidate had an available narrowing estimate." if status == "unavailable" else None
        ),
        "invalid_measurement_count": invalid_count,
    }
