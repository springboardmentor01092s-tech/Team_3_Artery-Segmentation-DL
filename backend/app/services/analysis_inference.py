"""Bridge the API process to the isolated, persistent CPU inference worker."""

from __future__ import annotations

import atexit
import base64
import json
import logging
import math
import os
import re
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import Settings

logger = logging.getLogger(__name__)
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[a-zA-Z]:[\\/]")


def _resolve_ml_executable(configured: Path) -> Path:
    raw = str(configured)
    if os.name != "nt" and _WINDOWS_ABSOLUTE_PATH.match(raw):
        raise InferenceUnavailable("A Windows ML executable cannot run with this Linux backend")
    # Venv executables are symlinks to their base Python. Preserve that link so
    # Python discovers the venv's site-packages instead of the base environment.
    return Path(os.path.abspath(configured))


class InferenceUnavailable(RuntimeError):
    """The isolated ML runtime could not safely complete inference."""


def _validate_percentage_narrowing(value: object, metadata: dict[str, Any], candidates: list[Any]) -> None:
    """Validate experimental mask-width metadata before it is persisted."""
    if not isinstance(value, dict):
        raise ValueError("percentage narrowing metadata is missing")
    if (
        value.get("algorithm_version") != "candidate-local-reference-predicted-mask-width-v4"
        or value.get("coordinate_system") != "original_image_pixel_grid"
        or value.get("measurement_unit") != "pixel"
        or not isinstance(value.get("disclaimer"), str)
        or "not a clinically calibrated lumen measurement" not in value["disclaimer"].lower()
    ):
        raise ValueError("percentage narrowing metadata is not safely labelled")
    if value.get("source_model_ids") != {
        "artery": "attention_unet",
        "stenosis": "unetpp_resnet34_stenosis",
    }:
        raise ValueError("percentage narrowing model sources do not match the inference run")
    source_thresholds = value.get("source_thresholds")
    attention_threshold = metadata["attention_unet"].get("threshold")
    stenosis_threshold = metadata["unetpp"].get("threshold")
    if not isinstance(source_thresholds, dict) or set(source_thresholds) != {"artery", "stenosis"}:
        raise ValueError("percentage narrowing thresholds are missing")
    expected_thresholds = {"artery": attention_threshold, "stenosis": stenosis_threshold}
    for name, expected in expected_thresholds.items():
        actual = source_thresholds.get(name)
        if (
            not isinstance(expected, (int, float)) or isinstance(expected, bool)
            or not math.isfinite(expected) or not isinstance(actual, (int, float))
            or isinstance(actual, bool) or not math.isfinite(actual)
            or not 0 <= actual <= 1 or not math.isclose(actual, expected, abs_tol=1e-9)
        ):
            raise ValueError("percentage narrowing thresholds do not match the inference run")

    measurements = value.get("measurements")
    if not isinstance(measurements, list) or len(measurements) != len(candidates):
        raise ValueError("percentage narrowing candidate measurements are invalid")
    candidate_ids = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("candidate identifiers are invalid")
        candidate_id = candidate.get("candidate_id")
        if isinstance(candidate_id, bool) or not isinstance(candidate_id, int) or candidate_id < 1:
            raise ValueError("candidate identifiers are invalid")
        candidate_ids.append(candidate_id)
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("candidate identifiers are invalid")
    seen: set[int] = set()
    available_count = 0
    for item in measurements:
        if not isinstance(item, dict):
            raise ValueError("candidate measurement is invalid")
        candidate_id = item.get("candidate_id")
        if (
            isinstance(candidate_id, bool) or not isinstance(candidate_id, int)
            or candidate_id not in candidate_ids or candidate_id in seen
        ):
            raise ValueError("candidate measurement association is invalid")
        seen.add(candidate_id)
        if item.get("status") == "available":
            available_count += 1
            reference = item.get("reference_predicted_mask_width_px")
            minimum = item.get("minimum_candidate_predicted_mask_width_px")
            percentage = item.get("estimated_narrowing_percent")
            values = (reference, minimum, percentage)
            if not all(
                isinstance(number, (int, float)) and not isinstance(number, bool) and math.isfinite(number)
                for number in values
            ):
                raise ValueError("candidate measurement values must be finite")
            if reference <= 0 or minimum <= 0 or minimum > reference or not 0 <= percentage <= 100:
                raise ValueError("candidate measurement values are out of range")
            expected_percentage = ((reference - minimum) / reference) * 100.0
            if not math.isclose(percentage, expected_percentage, rel_tol=1e-7, abs_tol=1e-7):
                raise ValueError("candidate percentage does not match its stored widths")
        elif item.get("status") == "unavailable":
            if not isinstance(item.get("unavailable_reason"), str) or not item["unavailable_reason"]:
                raise ValueError("unavailable candidate measurement has no reason")
            if any(key in item for key in (
                "reference_predicted_mask_width_px",
                "minimum_candidate_predicted_mask_width_px",
                "estimated_narrowing_percent",
            )):
                raise ValueError("unavailable candidate measurement contains a result")
        else:
            raise ValueError("candidate measurement status is invalid")
    expected_status = "unavailable" if not available_count else "available" if available_count == len(measurements) else "partial"
    if value.get("status") != expected_status:
        raise ValueError("percentage narrowing summary status is inconsistent")
    json.dumps(value, allow_nan=False)


class InferenceWorker:
    """Start the ML venv once, cache model weights there, and invoke a small CLI per run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._port: int | None = None
        self._token: str | None = None
        self._ready = False
        atexit.register(self.close)

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

    @staticmethod
    def _base_environment() -> dict[str, str]:
        # Do not pass the API process's database/authentication environment to ML code.
        allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "LANG")
        return {key: os.environ[key] for key in allowed if key in os.environ}

    def _start(self, settings: Settings) -> tuple[int, str]:
        with self._lock:
            if self._ready and self._process is not None and self._process.poll() is None:
                assert self._port is not None and self._token is not None
                return self._port, self._token
            if self._process is not None:
                self.close()
            executable = _resolve_ml_executable(settings.ml_python_executable)
            worker_script = self._repo_root() / "ml" / "inference" / "worker.py"
            if not executable.is_file() or not worker_script.is_file():
                raise InferenceUnavailable("The isolated ML runtime is not configured")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = int(probe.getsockname()[1])
            token = secrets.token_urlsafe(32)
            environment = self._base_environment()
            environment.update({
                "PYTHONIOENCODING": "utf-8",
                "ML_WORKER_PORT": str(port),
                "ML_WORKER_TOKEN": token,
                "ML_UPLOAD_ROOT": str(settings.upload_directory.resolve()),
                "ML_OUTPUT_ROOT": str(settings.analysis_output_directory.resolve()),
                "ML_STENOSIS_THRESHOLD": str(settings.analysis_stenosis_threshold),
                "ML_MIN_COMPONENT_AREA": str(settings.analysis_min_component_area),
                "ML_CPU_THREADS": str(settings.analysis_cpu_threads),
            })
            if settings.attention_checkpoint_path is not None:
                environment["ML_ATTENTION_CHECKPOINT"] = str(settings.attention_checkpoint_path.resolve())
            if settings.unetpp_checkpoint_path is not None:
                environment["ML_UNETPP_CHECKPOINT"] = str(settings.unetpp_checkpoint_path.resolve())
            try:
                self._process = subprocess.Popen(
                    [str(executable), str(worker_script)],
                    cwd=self._repo_root(),
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    # Worker stderr may include local paths or private model details.
                    stderr=subprocess.DEVNULL,
                )
            except OSError as exc:
                raise InferenceUnavailable("The isolated ML worker could not be started") from exc
            self._port, self._token, self._ready = port, token, False
            deadline = time.monotonic() + settings.analysis_worker_startup_timeout_seconds
            while time.monotonic() < deadline:
                if self._process is None or self._process.poll() is not None:
                    logger.error("Isolated ML worker exited during startup (exit_code=%s)", self._process.poll() if self._process else None)
                    self.close()
                    raise InferenceUnavailable("The isolated ML worker failed during startup")
                try:
                    self._request("GET", f"http://127.0.0.1:{port}/health", token, timeout=2)
                    self._ready = True
                    return port, token
                except (OSError, urllib.error.URLError, InferenceUnavailable):
                    time.sleep(0.25)
            self.close()
            raise InferenceUnavailable("The isolated ML worker did not become ready in time")

    @staticmethod
    def _request(method: str, url: str, token: str, *, timeout: int, data: bytes | None = None) -> bytes:
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (OSError, urllib.error.URLError) as exc:
            raise InferenceUnavailable("The isolated ML worker request failed") from exc

    def run(self, image_path: Path, run_directory: Path, run_id: uuid.UUID, settings: Settings) -> dict[str, Any]:
        port, token = self._start(settings)
        executable = _resolve_ml_executable(settings.ml_python_executable)
        environment = self._base_environment()
        environment.update({
            "PYTHONIOENCODING": "utf-8",
            "ML_WORKER_URL": f"http://127.0.0.1:{port}",
            "ML_WORKER_TOKEN": token,
            "ML_UPLOAD_ROOT": str(settings.upload_directory.resolve()),
            "ML_OUTPUT_ROOT": str(settings.analysis_output_directory.resolve()),
            "ML_REQUEST_TIMEOUT": str(settings.analysis_timeout_seconds),
        })
        command = [
            str(executable),
            str(self._repo_root() / "ml" / "inference" / "run_pipeline.py"),
            "--image-path", str(image_path.resolve()),
            "--output-directory", str(run_directory.resolve()),
            "--run-id", run_id.hex,
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=self._repo_root(),
                env=environment,
                capture_output=True,
                timeout=settings.analysis_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise InferenceUnavailable("Analysis exceeded the configured time limit") from exc
        except OSError as exc:
            raise InferenceUnavailable("The isolated inference command could not be started") from exc
        if len(completed.stdout) > settings.analysis_max_response_bytes:
            raise InferenceUnavailable("Inference response exceeded the configured size limit")
        if completed.returncode != 0:
            raise InferenceUnavailable("The inference pipeline failed")
        try:
            response = json.loads(completed.stdout.decode("utf-8"))
            self._validate_response(response, run_id, image_path)
        except (ValueError, TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InferenceUnavailable("The inference response failed validation") from exc
        return response

    @staticmethod
    def _validate_response(response: object, run_id: uuid.UUID, image_path: Path) -> None:
        if not isinstance(response, dict) or response.get("ok") is not True or response.get("schema_version") != 1:
            raise ValueError("invalid response")
        metadata = response.get("metadata")
        candidates = response.get("candidates")
        times = response.get("model_times")
        size = response.get("original_size")
        if not isinstance(metadata, dict) or not isinstance(candidates, list) or not isinstance(times, dict):
            raise ValueError("invalid metadata")
        if metadata.get("clinical_validation") is not False:
            raise ValueError("unsafe analysis metadata")
        gradcam_available = metadata.get("gradcam_available")
        if type(gradcam_available) is not bool:
            raise ValueError("invalid Grad-CAM status")
        if metadata.get("gradcam_target_layer") != "decoder.blocks.x_0_4.conv2.2":
            raise ValueError("unexpected Grad-CAM target layer")
        if metadata.get("gradcam_method") != "segmentation-targeted Grad-CAM":
            raise ValueError("unexpected Grad-CAM method")
        if gradcam_available and metadata.get("gradcam_unavailable_reason") is not None:
            raise ValueError("available Grad-CAM has an unavailable reason")
        if not gradcam_available and not isinstance(metadata.get("gradcam_unavailable_reason"), str):
            raise ValueError("unavailable Grad-CAM has no reason")
        if metadata.get("candidate_count") != len(candidates):
            raise ValueError("candidate count mismatch")
        if not isinstance(metadata.get("runtime_versions"), dict):
            raise ValueError("runtime versions are missing")
        model_data = {key: metadata.get(key) for key in ("attention_unet", "unetpp")}
        if not all(isinstance(value, dict) for value in model_data.values()):
            raise ValueError("model metadata is missing")
        if model_data["attention_unet"].get("model_id") != "attention_unet":
            raise ValueError("unexpected artery model")
        if model_data["unetpp"].get("model_id") != "unetpp_resnet34_stenosis":
            raise ValueError("unexpected stenosis model")
        _validate_percentage_narrowing(response.get("percentage_narrowing"), model_data, candidates)
        if set(times) != {"attention_unet_seconds", "unetpp_seconds", "gradcam_seconds"} or not all(
            isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 for value in times.values()
        ):
            raise ValueError("invalid model timings")
        total_time = metadata.get("total_pipeline_seconds")
        if not isinstance(total_time, (int, float)) or not math.isfinite(total_time) or total_time < 0:
            raise ValueError("invalid total timing")
        if not isinstance(size, list) or len(size) != 2 or not all(isinstance(x, int) and x > 0 for x in size):
            raise ValueError("invalid source dimensions")
        width, height = size
        if width * height > 40_000_000 or len(candidates) > 100_000:
            raise ValueError("response exceeds safe dimensions")
        if not all(isinstance(candidate, dict) for candidate in candidates):
            raise ValueError("invalid candidates")
        arrays = response.get("arrays")
        expected = {"artery_mask": "uint8", "stenosis_mask": "uint8", "stenosis_probability_map": "float32"}
        if not isinstance(arrays, dict) or set(arrays) != set(expected):
            raise ValueError("invalid arrays")
        for name, dtype_name in expected.items():
            item = arrays[name]
            if not isinstance(item, dict) or item.get("dtype") != dtype_name or item.get("shape") != [height, width]:
                raise ValueError("invalid array schema")
            raw = base64.b64decode(item.get("data", ""), validate=True)
            dtype = np.dtype(dtype_name)
            if len(raw) != width * height * dtype.itemsize:
                raise ValueError("invalid array length")
            array = np.frombuffer(raw, dtype=dtype)
            if name.endswith("mask") and not np.isin(array, (0, 1)).all():
                raise ValueError("invalid binary mask")
            if name == "stenosis_probability_map" and (
                not np.isfinite(array).all() or np.any((array < 0) | (array > 1))
            ):
                raise ValueError("invalid probabilities")
        artifacts = response.get("artifacts")
        expected_names = {
            "artery_mask.png", "stenosis_mask.png", "candidate_overlay.png",
            "combined_visualization.png", "candidates.json",
        }
        if gradcam_available:
            expected_names.add("gradcam.png")
        if not isinstance(artifacts, dict) or set(artifacts) != expected_names:
            raise ValueError("invalid artifact manifest")
        expected_root = run_id.hex
        for filename, key in artifacts.items():
            if key != f"{expected_root}/{filename}":
                raise ValueError("invalid artifact key")
        if not image_path.is_file():
            raise ValueError("source image disappeared")

    def close(self) -> None:
        process = self._process
        self._process = None
        self._ready = False
        self._port = None
        self._token = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


inference_worker = InferenceWorker()
