import base64
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from ml.inference.run_pipeline import _decode_visualization_artifacts
from ml.inference.worker import _build_artifacts


def make_result(heatmap):
    return SimpleNamespace(
        metadata={"gradcam_available": heatmap is not None, "gradcam_unavailable_reason": None if heatmap is not None else "not available"},
        candidate_overlay=np.zeros((12, 16, 3), dtype=np.uint8),
        combined_visualization=np.zeros((20, 24, 3), dtype=np.uint8),
        gradcam_heatmap=heatmap,
    )


def worker_artifact_payload(artifacts):
    return {
        name: {"encoding": "base64-png", "data": encoded}
        for name, encoded in artifacts.items()
    }


def test_worker_encodes_optional_gradcam_as_512_grayscale_display_png():
    heatmap = np.zeros((512, 512), dtype=np.float32)
    heatmap[100:120, 150:170] = 1.0

    artifacts, metadata = _build_artifacts(make_result(heatmap))

    assert "gradcam.png" in artifacts
    assert metadata["gradcam_available"] is True
    raw = base64.b64decode(artifacts["gradcam.png"], validate=True)
    from io import BytesIO

    with Image.open(BytesIO(raw)) as image:
        assert image.format == "PNG"
        assert image.mode == "L"
        assert image.size == (512, 512)
        values = np.asarray(image)
        assert values[110, 160] == 255
        assert values[0, 0] == 0


def test_worker_keeps_required_artifacts_when_gradcam_is_unavailable():
    artifacts, metadata = _build_artifacts(make_result(None))

    assert set(artifacts) == {"candidate_overlay.png", "combined_visualization.png"}
    assert metadata["gradcam_available"] is False
    assert metadata["gradcam_unavailable_reason"] == "not available"


def test_worker_encoding_failure_is_optional_and_preserves_segmentation_artifacts():
    invalid_heatmap = np.full((512, 512), np.nan, dtype=np.float32)

    artifacts, metadata = _build_artifacts(make_result(invalid_heatmap))

    assert set(artifacts) == {"candidate_overlay.png", "combined_visualization.png"}
    assert metadata["gradcam_available"] is False
    assert "could not be encoded" in metadata["gradcam_unavailable_reason"]


def test_cli_bridge_accepts_gradcam_when_available_and_when_unavailable():
    available, metadata = _build_artifacts(make_result(np.zeros((512, 512), dtype=np.float32)))
    available_metadata = {**metadata, "gradcam_available": True}
    decoded_available = _decode_visualization_artifacts(
        worker_artifact_payload(available),
        gradcam_available=available_metadata["gradcam_available"],
        width=16,
        height=12,
    )
    assert set(decoded_available) == {"candidate_overlay.png", "combined_visualization.png", "gradcam.png"}

    unavailable, unavailable_metadata = _build_artifacts(make_result(None))
    decoded_unavailable = _decode_visualization_artifacts(
        worker_artifact_payload(unavailable),
        gradcam_available=unavailable_metadata["gradcam_available"],
        width=16,
        height=12,
    )
    assert set(decoded_unavailable) == {"candidate_overlay.png", "combined_visualization.png"}


def test_cli_rejects_gradcam_dimension_mismatch():
    wrong_sized = np.zeros((256, 256), dtype=np.uint8)
    from ml.inference.worker import _png_base64

    payload = worker_artifact_payload({
        "candidate_overlay.png": _png_base64(np.zeros((12, 16, 3), dtype=np.uint8)),
        "combined_visualization.png": _png_base64(np.zeros((20, 24, 3), dtype=np.uint8)),
        "gradcam.png": _png_base64(wrong_sized),
    })
    with pytest.raises(ValueError, match="512x512"):
        _decode_visualization_artifacts(payload, gradcam_available=True, width=16, height=12)
