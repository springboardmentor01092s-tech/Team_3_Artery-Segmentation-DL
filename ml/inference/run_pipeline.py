"""One-image CLI bridge to the persistent isolated ML worker."""

from __future__ import annotations

import argparse
import base64
from io import BytesIO
import json
import math
import os
import urllib.request
import uuid
from pathlib import Path

import numpy as np
from PIL import Image


ARRAY_SPEC = {
    "artery_mask": ("uint8", 1),
    "stenosis_mask": ("uint8", 1),
    "stenosis_probability_map": ("float32", 4),
}
REQUIRED_ARTIFACTS = (
    "artery_mask.png", "stenosis_mask.png", "candidate_overlay.png", "combined_visualization.png", "candidates.json",
)
OPTIONAL_ARTIFACTS = ("gradcam.png",)
BASE_WORKER_ARTIFACTS = {"candidate_overlay.png", "combined_visualization.png"}


def _decode_visualization_artifacts(
    worker_artifacts: object,
    *,
    gradcam_available: bool,
    width: int,
    height: int,
) -> dict[str, bytes]:
    """Validate the exact required/optional worker PNG set before atomic writes."""
    if not isinstance(worker_artifacts, dict):
        raise ValueError("invalid visualization artifacts")
    expected = BASE_WORKER_ARTIFACTS | ({"gradcam.png"} if gradcam_available else set())
    if set(worker_artifacts) != expected:
        raise ValueError("visualization artifacts do not match Grad-CAM availability")

    validated: dict[str, bytes] = {}
    for filename, item in worker_artifacts.items():
        if not isinstance(item, dict) or item.get("encoding") != "base64-png":
            raise ValueError("invalid visualization encoding")
        content = base64.b64decode(item.get("data", ""), validate=True)
        with Image.open(BytesIO(content)) as image:
            if image.format != "PNG":
                raise ValueError("visualization is not PNG")
            dimensions = image.size
            image.verify()
        if filename == "candidate_overlay.png" and dimensions != (width, height):
            raise ValueError("overlay dimensions do not match source")
        if filename == "gradcam.png" and dimensions != (512, 512):
            raise ValueError("Grad-CAM dimensions must be 512x512")
        if filename == "combined_visualization.png" and not all(1 <= dimension <= 4096 for dimension in dimensions):
            raise ValueError("combined visualization dimensions are invalid")
        validated[filename] = content
    return validated


def _validate_percentage_narrowing(value: object, candidates: object) -> dict[str, object]:
    """Validate JSON-safe measurement metadata without trusting worker output."""
    if not isinstance(value, dict):
        raise ValueError("percentage narrowing metadata is missing")
    if value.get("algorithm_version") != "candidate-local-reference-predicted-mask-width-v4":
        raise ValueError("unsupported percentage narrowing algorithm version")
    if value.get("status") not in {"available", "partial", "unavailable"}:
        raise ValueError("invalid percentage narrowing status")
    if value.get("coordinate_system") != "original_image_pixel_grid" or value.get("measurement_unit") != "pixel":
        raise ValueError("invalid percentage narrowing coordinate system")
    if not isinstance(value.get("disclaimer"), str) or "not a clinically calibrated lumen measurement" not in value["disclaimer"].lower():
        raise ValueError("percentage narrowing disclaimer is missing")
    items = value.get("measurements")
    if not isinstance(items, list) or not isinstance(candidates, list) or len(items) != len(candidates):
        raise ValueError("percentage narrowing candidate list is invalid")
    candidate_ids = {item.get("candidate_id") for item in candidates if isinstance(item, dict)}
    if len(candidate_ids) != len(candidates):
        raise ValueError("candidate IDs are invalid")
    seen_ids: set[int] = set()
    available_count = 0
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("percentage narrowing measurement is invalid")
        candidate_id = item.get("candidate_id")
        if isinstance(candidate_id, bool) or not isinstance(candidate_id, int) or candidate_id not in candidate_ids or candidate_id in seen_ids:
            raise ValueError("percentage narrowing candidate association is invalid")
        seen_ids.add(candidate_id)
        if item.get("status") == "available":
            available_count += 1
            reference = item.get("reference_predicted_mask_width_px")
            lesion = item.get("minimum_candidate_predicted_mask_width_px")
            percentage = item.get("estimated_narrowing_percent")
            numbers = (reference, lesion, percentage)
            if not all(isinstance(number, (int, float)) and not isinstance(number, bool) and math.isfinite(number) for number in numbers):
                raise ValueError("percentage narrowing numeric values must be finite")
            if reference <= 0 or lesion <= 0 or lesion > reference or not 0 <= percentage <= 100:
                raise ValueError("percentage narrowing numeric values are out of range")
            expected = ((reference - lesion) / reference) * 100.0
            if not math.isclose(float(percentage), expected, rel_tol=1e-7, abs_tol=1e-7):
                raise ValueError("percentage narrowing formula does not match stored widths")
        elif item.get("status") == "unavailable":
            if not isinstance(item.get("unavailable_reason"), str) or not item["unavailable_reason"]:
                raise ValueError("unavailable measurement has no reason")
            if any(key in item for key in (
                "reference_predicted_mask_width_px", "minimum_candidate_predicted_mask_width_px", "estimated_narrowing_percent"
            )):
                raise ValueError("unavailable measurement cannot contain numeric results")
        else:
            raise ValueError("invalid candidate measurement status")
    expected_status = "unavailable" if available_count == 0 else "available" if available_count == len(items) else "partial"
    if value["status"] != expected_status:
        raise ValueError("percentage narrowing summary status does not match its measurements")
    json.dumps(value, allow_nan=False)
    return value


def _atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("xb") as target:
        target.write(content)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-path", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    try:
        run_id = uuid.UUID(args.run_id)
        run_dir = args.output_directory.resolve(strict=True)
        output_root = Path(os.environ["ML_OUTPUT_ROOT"]).resolve(strict=True)
        if run_dir.parent != output_root or run_dir.name != run_id.hex:
            raise ValueError("invalid run output directory")
        source = args.image_path.resolve(strict=True)
        upload_root = Path(os.environ["ML_UPLOAD_ROOT"]).resolve(strict=True)
        if source.parent != upload_root or not source.is_file():
            raise ValueError("invalid source image path")
        worker_url = os.environ["ML_WORKER_URL"].rstrip("/")
        token = os.environ["ML_WORKER_TOKEN"]
        request = urllib.request.Request(
            worker_url + "/predict",
            data=json.dumps({"image_path": str(source)}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=int(os.environ.get("ML_REQUEST_TIMEOUT", "600"))) as response:
            payload = json.loads(response.read())
        if not isinstance(payload, dict) or payload.get("ok") is not True or payload.get("schema_version") != 1:
            raise ValueError("invalid inference response")
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict) or type(metadata.get("gradcam_available")) is not bool:
            raise ValueError("invalid Grad-CAM status metadata")
        gradcam_available = metadata["gradcam_available"]
        width, height = payload.get("original_size", [0, 0])
        if not (isinstance(width, int) and isinstance(height, int) and 1 <= width * height <= 40_000_000):
            raise ValueError("invalid output dimensions")

        arrays = payload.get("arrays")
        if not isinstance(arrays, dict) or set(arrays) != set(ARRAY_SPEC):
            raise ValueError("invalid output arrays")
        parsed: dict[str, np.ndarray] = {}
        for name, (dtype, itemsize) in ARRAY_SPEC.items():
            item = arrays[name]
            if not isinstance(item, dict) or item.get("dtype") != dtype or item.get("shape") != [height, width]:
                raise ValueError("invalid output array metadata")
            raw = base64.b64decode(item["data"], validate=True)
            if len(raw) != width * height * itemsize:
                raise ValueError("invalid output array length")
            parsed[name] = np.frombuffer(raw, dtype=np.dtype(dtype)).reshape((height, width)).copy()
        if not np.isin(parsed["artery_mask"], (0, 1)).all() or not np.isin(parsed["stenosis_mask"], (0, 1)).all():
            raise ValueError("mask values are not binary")
        probabilities = parsed["stenosis_probability_map"]
        if not np.isfinite(probabilities).all() or np.any((probabilities < 0) | (probabilities > 1)):
            raise ValueError("probabilities are invalid")

        for name in ("artery_mask", "stenosis_mask"):
            stream = BytesIO()
            Image.fromarray(parsed[name] * 255, mode="L").save(stream, format="PNG")
            _atomic_write(run_dir / f"{name}.png", stream.getvalue())
        visualization_artifacts = _decode_visualization_artifacts(
            payload.get("artifacts"),
            gradcam_available=gradcam_available,
            width=width,
            height=height,
        )
        for filename, content in visualization_artifacts.items():
            _atomic_write(run_dir / filename, content)
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("invalid candidate list")
        percentage_narrowing = _validate_percentage_narrowing(payload.get("percentage_narrowing"), candidates)
        candidates_content = json.dumps(
            {"label": "Predicted stenosis candidates; not confirmed stenoses", "candidates": candidates},
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        _atomic_write(run_dir / "candidates.json", candidates_content)

        response_payload = {
            "ok": True,
            "schema_version": 1,
            "metadata": payload.get("metadata"),
            "model_times": payload.get("model_times"),
            "original_size": [width, height],
            "arrays": {
                name: {
                    "dtype": ARRAY_SPEC[name][0],
                    "shape": [height, width],
                    "data": base64.b64encode(array.tobytes()).decode("ascii"),
                }
                for name, array in parsed.items()
            },
            "artifacts": {
                name: f"{run_id.hex}/{name}"
                for name in (*REQUIRED_ARTIFACTS, *(OPTIONAL_ARTIFACTS if gradcam_available else ()))
            },
            "candidates": candidates,
            "percentage_narrowing": percentage_narrowing,
        }
        print(json.dumps(response_payload, allow_nan=False, separators=(",", ":")))
        return 0
    except Exception:
        print(json.dumps({"ok": False, "error": "inference_bridge_failed"}, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
