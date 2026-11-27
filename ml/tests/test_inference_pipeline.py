from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

import ml.inference.pipeline as pipeline_module
from ml.inference.pipeline import (
    CombinedInferencePipeline,
    PipelineInputError,
    _combined_visualization,
    extract_candidates,
)


class FakeAttentionAdapter:
    threshold = 0.50

    def __init__(self) -> None:
        self.received = None

    def predict(self, image):
        self.received = image
        return SimpleNamespace(
            mask=np.zeros((1, 256, 256), dtype=np.uint8),
            metadata={"model_id": "test_attention", "threshold": self.threshold},
        )


class FakeUNetPPAdapter:
    def __init__(self, threshold: float = 0.20) -> None:
        self.threshold = threshold
        self.received = None

    def predict(self, image):
        self.received = image
        probabilities = np.full((1, 512, 512), 0.1, dtype=np.float32)
        mask = np.zeros((1, 512, 512), dtype=np.uint8)
        mask[0, 10:13, 20:23] = 1
        probabilities[0, 10:13, 20:23] = 0.8
        return SimpleNamespace(
            probability_map=probabilities,
            mask=mask,
            metadata={"model_id": "test_unetpp", "threshold": self.threshold},
        )


class FakeGradCAMUNetPPAdapter(FakeUNetPPAdapter):
    def __init__(self, threshold: float = 0.20, *, fail_gradcam: bool = False) -> None:
        super().__init__(threshold)
        self.fail_gradcam = fail_gradcam
        self.gradcam_received = None

    def gradcam(self, image, *, prediction_mask):
        self.gradcam_received = (image, prediction_mask)
        if self.fail_gradcam:
            raise RuntimeError("test explanation failure")
        heatmap = np.zeros((512, 512), dtype=np.float32)
        heatmap[10:13, 20:23] = 1.0
        return SimpleNamespace(
            heatmap=heatmap,
            metadata={
                "target_layer": "decoder.blocks.x_0_4.conv2.2",
                "method": "segmentation-targeted Grad-CAM",
                "target_score": "mean logits over predicted stenosis pixels; maximum logit when the mask is empty",
            },
        )


def test_pipeline_passes_original_to_both_models_and_returns_aligned_outputs() -> None:
    original = Image.fromarray(np.full((60, 80), 91, dtype=np.uint8), mode="L")
    attention = FakeAttentionAdapter()
    unetpp = FakeUNetPPAdapter(threshold=0.35)
    pipeline = CombinedInferencePipeline(
        attention_adapter=attention,
        unetpp_adapter=unetpp,
        stenosis_threshold=0.35,
        minimum_component_area=5,
    )

    result = pipeline.predict(original)

    assert attention.received is original
    assert unetpp.received is original
    assert result.original_image.shape == (60, 80)
    assert result.artery_mask.shape == (60, 80)
    assert result.stenosis_mask.shape == (60, 80)
    assert result.stenosis_probability_map.shape == (60, 80)
    assert result.candidate_overlay.shape == (60, 80, 3)
    assert result.combined_visualization.ndim == 3
    assert result.combined_visualization.shape[2] == 3
    assert set(np.unique(result.artery_mask)).issubset({0, 1})
    assert set(np.unique(result.stenosis_mask)).issubset({0, 1})
    assert np.isfinite(result.stenosis_probability_map).all()
    assert result.metadata["unetpp"]["threshold"] == 0.35
    assert result.metadata["gradcam_available"] is False
    assert result.candidates[0].label == "Predicted stenosis candidate 1"
    assert result.candidates[0].area_pixels == 9
    assert result.percentage_narrowing["status"] == "unavailable"
    assert result.percentage_narrowing["measurements"][0]["status"] == "unavailable"
    assert result.percentage_narrowing["source_thresholds"] == {"artery": 0.5, "stenosis": 0.35}


def test_candidate_components_use_eight_connectivity_area_and_mean_probability() -> None:
    mask = np.zeros((10, 10), dtype=np.uint8)
    diagonal_component = [(1, 1), (2, 2), (3, 3), (3, 4), (4, 4)]
    for y, x in diagonal_component:
        mask[y, x] = 1
    mask[7, 1:5] = 1  # Exactly four pixels; removed by the default minimum area.
    probability = np.zeros((10, 10), dtype=np.float32)
    for index, (y, x) in enumerate(diagonal_component):
        probability[y, x] = 0.2 + 0.1 * index
    probability[7, 1:5] = 0.9

    candidates = extract_candidates(mask, probability, minimum_area=5)

    assert len(candidates) == 1
    assert candidates[0]["model_bbox"] == (1, 1, 4, 4)
    assert candidates[0]["model_centroid"] == pytest.approx((2.8, 2.6))
    assert candidates[0]["area_pixels"] == 5
    assert candidates[0]["mean_probability"] == pytest.approx(0.4)


def test_pipeline_returns_gradcam_separately_when_available() -> None:
    image = Image.fromarray(np.full((60, 80), 91, dtype=np.uint8), mode="L")
    unetpp = FakeGradCAMUNetPPAdapter()
    pipeline = CombinedInferencePipeline(attention_adapter=FakeAttentionAdapter(), unetpp_adapter=unetpp)

    result = pipeline.predict(image)

    assert result.gradcam_heatmap is not None
    assert result.gradcam_heatmap.shape == (512, 512)
    assert result.metadata["gradcam_available"] is True
    assert result.metadata["gradcam_method"] == "segmentation-targeted Grad-CAM"
    assert result.model_times["gradcam_seconds"] >= 0
    assert unetpp.gradcam_received[0] is image
    assert unetpp.gradcam_received[1] is not None
    assert result.stenosis_mask.shape == (60, 80)


def test_gradcam_failure_does_not_fail_or_replace_segmentation_outputs() -> None:
    image = Image.fromarray(np.full((60, 80), 91, dtype=np.uint8), mode="L")
    unetpp = FakeGradCAMUNetPPAdapter(fail_gradcam=True)
    pipeline = CombinedInferencePipeline(attention_adapter=FakeAttentionAdapter(), unetpp_adapter=unetpp)

    result = pipeline.predict(image)

    assert result.gradcam_heatmap is None
    assert result.metadata["gradcam_available"] is False
    assert result.metadata["gradcam_unavailable_reason"]
    assert result.stenosis_mask.shape == (60, 80)
    assert result.candidates[0].area_pixels == 9


def test_percentage_narrowing_failure_does_not_fail_segmentation(monkeypatch) -> None:
    image = Image.fromarray(np.full((60, 80), 91, dtype=np.uint8), mode="L")

    def fail_measurement(*_args, **_kwargs):
        raise RuntimeError("synthetic geometry failure")

    monkeypatch.setattr(pipeline_module, "estimate_percentage_narrowing", fail_measurement)
    result = CombinedInferencePipeline(
        attention_adapter=FakeAttentionAdapter(),
        unetpp_adapter=FakeUNetPPAdapter(),
    ).predict(image)

    assert result.artery_mask.shape == (60, 80)
    assert result.stenosis_mask.shape == (60, 80)
    assert result.candidates
    assert result.percentage_narrowing["status"] == "unavailable"
    assert result.percentage_narrowing["measurements"][0]["status"] == "unavailable"


def test_combined_visualization_scales_binary_mask_foreground_to_white() -> None:
    original = np.zeros((8, 8), dtype=np.uint8)
    artery_mask = np.zeros((8, 8), dtype=np.uint8)
    artery_mask[2:6, 2:6] = 1
    stenosis_mask = np.zeros((8, 8), dtype=np.uint8)
    stenosis_mask[3:5, 3:5] = 1
    overlay = np.zeros((8, 8, 3), dtype=np.uint8)

    combined = _combined_visualization(original, artery_mask, stenosis_mask, overlay)

    # Layout: 2x2 panels, each with a 30-pixel title band.
    assert tuple(combined[32, 10]) == (255, 255, 255)  # artery foreground
    assert tuple(combined[30, 8]) == (0, 0, 0)  # artery background
    assert tuple(combined[71, 3]) == (255, 255, 255)  # stenosis foreground
    assert tuple(combined[68, 0]) == (0, 0, 0)  # stenosis background


def test_pipeline_passes_configured_threshold_to_default_unetpp_adapter(monkeypatch) -> None:
    captured = {}
    fake_unetpp = FakeUNetPPAdapter(threshold=0.37)

    def fake_constructor(*, threshold: float):
        captured["threshold"] = threshold
        return fake_unetpp

    monkeypatch.setattr(pipeline_module, "UNetPPAdapter", fake_constructor)
    CombinedInferencePipeline(attention_adapter=FakeAttentionAdapter(), stenosis_threshold=0.37)

    assert captured["threshold"] == 0.37


def test_invalid_image_is_rejected_before_model_calls(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"not an image")
    attention = FakeAttentionAdapter()
    unetpp = FakeUNetPPAdapter()
    pipeline = CombinedInferencePipeline(attention_adapter=attention, unetpp_adapter=unetpp)

    with pytest.raises(PipelineInputError, match="unreadable or corrupted"):
        pipeline.predict(corrupt)
    assert attention.received is None
    assert unetpp.received is None


def test_invalid_mask_and_component_area_are_rejected() -> None:
    with pytest.raises(ValueError, match="binary values"):
        extract_candidates(np.array([[0, 2]], dtype=np.uint8), np.array([[0.1, 0.2]], dtype=np.float32))
    with pytest.raises(ValueError, match="at least 1"):
        extract_candidates(np.zeros((2, 2), dtype=np.uint8), np.zeros((2, 2), dtype=np.float32), minimum_area=0)
