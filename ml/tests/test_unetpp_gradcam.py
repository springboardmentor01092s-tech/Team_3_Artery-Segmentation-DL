from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image
from torch import nn

from ml.inference.unetpp import GRADCAM_TARGET_LAYER, UNetPPAdapter


class ToyGradCAMModel(nn.Module):
    def __init__(self, *, empty_logits: bool = False, fail_after_target: bool = False) -> None:
        super().__init__()
        self.decoder = nn.Module()
        self.decoder.blocks = nn.Module()
        self.decoder.blocks.x_0_4 = nn.Module()
        self.decoder.blocks.x_0_4.conv2 = nn.Sequential(nn.Identity(), nn.Identity(), nn.ReLU())
        self.scale = nn.Parameter(torch.tensor(1.0))
        self.empty_logits = empty_logits
        self.fail_after_target = fail_after_target
        self.input_ptrs: list[int] = []

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        self.input_ptrs.append(image.data_ptr())
        activation = self.decoder.blocks.x_0_4.conv2[2](image * self.scale)
        if self.fail_after_target:
            raise RuntimeError("toy forward failure")
        if self.empty_logits:
            return activation * 0.0 - 2.0 * self.scale
        return activation


def make_adapter(*, empty_logits: bool = False, fail_after_target: bool = False) -> UNetPPAdapter:
    adapter = UNetPPAdapter.__new__(UNetPPAdapter)
    adapter.threshold = 0.20
    adapter.device = torch.device("cpu")
    adapter.checkpoint_path = Path("toy-checkpoint.pt")
    adapter._model = ToyGradCAMModel(empty_logits=empty_logits, fail_after_target=fail_after_target).eval()
    adapter._gradcam_target_layer = adapter._model.get_submodule(GRADCAM_TARGET_LAYER)
    values = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
    values[:, :, 80:280, 120:320] = 1.0
    adapter.preprocess = lambda _image: values  # type: ignore[method-assign]
    return adapter


def test_gradcam_returns_finite_normalized_512_heatmap_and_cleans_hook() -> None:
    adapter = make_adapter()
    target = adapter._gradcam_target_layer
    original_hooks = len(target._forward_hooks)

    result = adapter.gradcam(Image.new("L", (8, 8)))

    assert result.heatmap.shape == (512, 512)
    assert result.heatmap.dtype == np.float32
    assert np.isfinite(result.heatmap).all()
    assert 0.0 <= float(result.heatmap.min()) <= float(result.heatmap.max()) <= 1.0
    assert result.metadata["target_layer"] == GRADCAM_TARGET_LAYER
    assert len(target._forward_hooks) == original_hooks
    assert all(parameter.grad is None for parameter in adapter._model.parameters())


def test_empty_prediction_mask_uses_maximum_logit_fallback_safely() -> None:
    adapter = make_adapter(empty_logits=True)

    result = adapter.gradcam(Image.new("L", (8, 8)))

    assert result.metadata["target_score_fallback"] is True
    assert result.metadata["predicted_pixel_count"] == 0
    assert result.heatmap.shape == (512, 512)
    assert np.isfinite(result.heatmap).all()
    assert set(np.unique(result.heatmap)).issubset({0.0})


def test_constant_zero_heatmap_is_normalized_to_finite_zeros() -> None:
    adapter = make_adapter()
    adapter.preprocess = lambda _image: torch.ones((1, 1, 512, 512), dtype=torch.float32)  # type: ignore[method-assign]

    result = adapter.gradcam(Image.new("L", (8, 8)))

    assert np.isfinite(result.heatmap).all()
    assert np.array_equal(result.heatmap, np.zeros((512, 512), dtype=np.float32))


def test_hooks_and_gradients_are_cleaned_after_forward_failure() -> None:
    adapter = make_adapter(fail_after_target=True)
    target = adapter._gradcam_target_layer
    original_hooks = len(target._forward_hooks)

    with pytest.raises(RuntimeError, match="toy forward failure"):
        adapter.gradcam(Image.new("L", (8, 8)))

    assert len(target._forward_hooks) == original_hooks
    assert all(parameter.grad is None for parameter in adapter._model.parameters())


def test_normal_prediction_remains_identical_before_and_after_gradcam() -> None:
    adapter = make_adapter()
    image = Image.new("L", (8, 8))

    before = adapter.predict(image)
    adapter.gradcam(image, prediction_mask=before.mask)
    after = adapter.predict(image)

    np.testing.assert_array_equal(before.mask, after.mask)
    np.testing.assert_array_equal(before.probability_map, after.probability_map)


def test_pipeline_can_reuse_the_same_preprocessed_tensor_for_prediction_and_gradcam() -> None:
    adapter = make_adapter()
    image = Image.new("L", (8, 8))

    prediction, prepared_input = adapter.predict_with_input(image)
    adapter.gradcam(image, prediction_mask=prediction.mask, preprocessed_input=prepared_input)

    assert adapter._model.input_ptrs[-2:] == [prepared_input.data_ptr(), prepared_input.data_ptr()]


def test_gradcam_rejects_inference_mode() -> None:
    adapter = make_adapter()
    with torch.inference_mode(), pytest.raises(RuntimeError, match="cannot run inside"):
        adapter.gradcam(Image.new("L", (8, 8)))
