"""Private loopback inference worker; model weights stay resident in this process."""

from __future__ import annotations

import hmac
import io
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from PIL import Image


def _png_base64(array: np.ndarray) -> str:
    from base64 import b64encode

    image_array = np.asarray(array, dtype=np.uint8)
    image = Image.fromarray(image_array, mode="RGB" if image_array.ndim == 3 else "L")
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return b64encode(stream.getvalue()).decode("ascii")


def _gradcam_png_base64(heatmap: np.ndarray) -> str:
    """Encode a normalized 512x512 heatmap as a display-scaled grayscale PNG."""
    values = np.asarray(heatmap, dtype=np.float32)
    if values.shape != (512, 512) or not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
        raise ValueError("invalid Grad-CAM heatmap")
    pixels = np.rint(values * 255).astype(np.uint8)
    encoded = _png_base64(pixels)
    from base64 import b64decode

    with Image.open(io.BytesIO(b64decode(encoded, validate=True))) as check:
        if check.format != "PNG" or check.mode != "L" or check.size != (512, 512):
            raise ValueError("invalid Grad-CAM PNG")
        check.verify()
    return encoded


def _build_artifacts(result) -> tuple[dict[str, str], dict[str, object]]:
    """Build required visual artifacts and add Grad-CAM only when safely encoded."""
    metadata = dict(result.metadata)
    artifacts = {
        "candidate_overlay.png": _png_base64(result.candidate_overlay),
        "combined_visualization.png": _png_base64(result.combined_visualization),
    }
    heatmap = getattr(result, "gradcam_heatmap", None)
    if heatmap is not None:
        try:
            artifacts["gradcam.png"] = _gradcam_png_base64(heatmap)
            metadata["gradcam_available"] = True
            metadata["gradcam_unavailable_reason"] = None
        except Exception:
            # Keep successful segmentation artifacts if optional XAI encoding fails.
            metadata["gradcam_available"] = False
            metadata["gradcam_unavailable_reason"] = (
                "Grad-CAM visualization could not be encoded; segmentation results are available."
            )
    else:
        metadata["gradcam_available"] = False
        if not isinstance(metadata.get("gradcam_unavailable_reason"), str) or not metadata["gradcam_unavailable_reason"]:
            metadata["gradcam_unavailable_reason"] = (
                "Grad-CAM was unavailable for this run; segmentation results are available."
            )
    return artifacts, metadata


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))

    import torch
    import segmentation_models_pytorch as smp

    from ml.inference.attention_unet import AttentionUNetAdapter
    from ml.inference.pipeline import CombinedInferencePipeline
    from ml.inference.unetpp import UNetPPAdapter

    upload_root = Path(os.environ["ML_UPLOAD_ROOT"]).resolve()
    token = os.environ["ML_WORKER_TOKEN"]
    torch.set_num_threads(int(os.environ.get("ML_CPU_THREADS", "2")))
    attention_checkpoint = os.environ.get("ML_ATTENTION_CHECKPOINT")
    unetpp_checkpoint = os.environ.get("ML_UNETPP_CHECKPOINT")
    threshold = float(os.environ.get("ML_STENOSIS_THRESHOLD", "0.20"))
    pipeline = CombinedInferencePipeline(
        attention_adapter=AttentionUNetAdapter(checkpoint_path=attention_checkpoint) if attention_checkpoint else AttentionUNetAdapter(),
        unetpp_adapter=UNetPPAdapter(checkpoint_path=unetpp_checkpoint, threshold=threshold) if unetpp_checkpoint else UNetPPAdapter(threshold=threshold),
        stenosis_threshold=float(os.environ.get("ML_STENOSIS_THRESHOLD", "0.20")),
        minimum_component_area=int(os.environ.get("ML_MIN_COMPONENT_AREA", "5")),
    )
    inference_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *args: object) -> None:
            # Avoid logging request bodies, filesystem paths or the internal token.
            return

        def _authorized(self) -> bool:
            value = self.headers.get("Authorization", "")
            return hmac.compare_digest(value, f"Bearer {token}")

        def _json(self, code: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/health" or not self._authorized():
                self._json(404, {"error": "not_found"})
                return
            self._json(200, {"ready": True})

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/predict" or not self._authorized():
                self._json(404, {"error": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 16_384:
                    raise ValueError("invalid request size")
                request = json.loads(self.rfile.read(length))
                source = Path(request["image_path"]).resolve(strict=True)
                if source.parent != upload_root or not source.is_file():
                    raise ValueError("source is outside upload storage")
                # Keep CPU memory bounded; requests share the resident model sequentially.
                with inference_lock:
                    result = pipeline.predict(source)
                visualization_artifacts, response_metadata = _build_artifacts(result)
                arrays = {
                    "artery_mask": np.asarray(result.artery_mask, dtype=np.uint8),
                    "stenosis_mask": np.asarray(result.stenosis_mask, dtype=np.uint8),
                    "stenosis_probability_map": np.asarray(result.stenosis_probability_map, dtype=np.float32),
                }
                payload: dict[str, object] = {
                    "ok": True,
                    "schema_version": 1,
                    "metadata": response_metadata,
                    "model_times": result.model_times,
                    "percentage_narrowing": result.percentage_narrowing,
                    "arrays": {},
                    "artifacts": visualization_artifacts,
                    "candidates": [
                        {
                            "candidate_id": item.candidate_id,
                            "label": item.label,
                            "bbox": list(item.bbox),
                            "centroid": list(item.centroid),
                            "area_pixels": item.area_pixels,
                            "mean_probability": item.mean_probability,
                            "measurement_grid": "512x512 model pixels",
                        }
                        for item in result.candidates
                    ],
                    "original_size": [int(result.original_image.shape[1]), int(result.original_image.shape[0])],
                }
                payload["metadata"]["candidate_count"] = len(result.candidates)
                payload["metadata"]["runtime_versions"] = {
                    "torch": str(torch.__version__),
                    "torchvision": str(__import__("torchvision").__version__),
                    "segmentation_models_pytorch": str(smp.__version__),
                    "numpy": str(np.__version__),
                }
                from base64 import b64encode

                payload_arrays = payload["arrays"]
                assert isinstance(payload_arrays, dict)
                for name, array in arrays.items():
                    payload_arrays[name] = {
                        "dtype": str(array.dtype),
                        "shape": list(array.shape),
                        "data": b64encode(np.ascontiguousarray(array).tobytes()).decode("ascii"),
                    }
                for filename, encoded in payload["artifacts"].items():
                    payload["artifacts"][filename] = {"encoding": "base64-png", "data": encoded}
                self._json(200, payload)
            except Exception:
                self._json(422, {"error": "inference_failed"})

    server = ThreadingHTTPServer(("127.0.0.1", int(os.environ["ML_WORKER_PORT"])), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
