import numpy as np
import pytest
import torch

from app.arcade_ml.explain import integrated_gradients_attribution


class TinySegmenter(torch.nn.Module):
    def forward(self, image):
        return image[:, :1] * 8 - 2


def test_integrated_gradients_returns_finite_original_resolution_map():
    image = np.full((20, 30, 3), 255, dtype=np.uint8)
    heat, metadata = integrated_gradients_attribution(
        TinySegmenter(), image, 16, torch.device("cpu"), threshold=0.5, steps=4,
    )
    assert heat.shape == (20, 30)
    assert np.isfinite(heat).all()
    assert heat.max() == pytest.approx(1.0)
    assert metadata["method"] == "integrated_gradients"
    assert "not clinical confidence" in metadata["interpretation"]


def test_integrated_gradients_refuses_empty_predicted_foreground():
    image = np.zeros((12, 12, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="no foreground"):
        integrated_gradients_attribution(
            TinySegmenter(), image, 16, torch.device("cpu"), threshold=0.99, steps=4,
        )


def test_integrated_gradients_rejects_invalid_step_count():
    image = np.ones((8, 8, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="Invalid"):
        integrated_gradients_attribution(
            TinySegmenter(), image, 8, torch.device("cpu"), steps=1,
        )
