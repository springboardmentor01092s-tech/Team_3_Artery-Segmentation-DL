from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from ml.inference.unetpp import (
    DEFAULT_CHECKPOINT_PATH,
    UNetPPAdapter,
    InvalidInferenceInput,
)


@pytest.fixture(scope="module")
def adapter():
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(min(previous_threads, 2))
    try:
        yield UNetPPAdapter(DEFAULT_CHECKPOINT_PATH, threshold=0.20)
    finally:
        torch.set_num_threads(previous_threads)


def test_existing_checkpoint_loads_strictly_on_cpu(adapter: UNetPPAdapter) -> None:
    assert adapter._model.training is False
    assert all(parameter.device.type == "cpu" for parameter in adapter._model.parameters())
    assert isinstance(adapter._model.get_submodule("decoder.blocks.x_0_4.conv2.2"), torch.nn.ReLU)


def test_synthetic_image_inference_returns_finite_probabilities_and_binary_mask(
    adapter: UNetPPAdapter,
) -> None:
    synthetic = Image.fromarray(np.full((160, 240, 3), 127, dtype=np.uint8), mode="RGB")

    result = adapter.predict(synthetic)

    assert result.probability_map.shape == (1, 512, 512)
    assert result.probability_map.dtype == np.float32
    assert np.isfinite(result.probability_map).all()
    assert float(result.probability_map.min()) >= 0.0
    assert float(result.probability_map.max()) <= 1.0
    assert result.mask.shape == (1, 512, 512)
    assert result.mask.dtype == np.uint8
    assert set(np.unique(result.mask)).issubset({0, 1})
    assert result.metadata["device"] == "cpu"
    assert result.metadata["threshold"] == 0.20
    assert result.metadata["threshold_is_provisional"] is True


def test_preprocessing_matches_declared_normalization() -> None:
    image = Image.fromarray(np.full((20, 40), 255, dtype=np.uint8), mode="L")

    tensor = UNetPPAdapter.preprocess(image)

    expected = (1.0 - 0.449) / 0.226
    assert tuple(tensor.shape) == (1, 1, 512, 512)
    assert tensor.dtype == torch.float32
    assert torch.allclose(tensor, torch.full_like(tensor, expected), atol=1e-6)


def test_corrupt_and_unsupported_inputs_are_rejected(tmp_path: Path) -> None:
    corrupt_file = tmp_path / "corrupt.png"
    corrupt_file.write_bytes(b"not a valid image")

    with pytest.raises(InvalidInferenceInput, match="unreadable or corrupted"):
        UNetPPAdapter.preprocess(corrupt_file)
    with pytest.raises(InvalidInferenceInput, match="path or a PIL image"):
        UNetPPAdapter.preprocess(object())  # type: ignore[arg-type]


def test_mismatched_checkpoint_is_rejected_strictly(tmp_path: Path) -> None:
    bad_checkpoint = tmp_path / "bad_checkpoint.pt"
    torch.save({"model_state_dict": {}}, bad_checkpoint)

    with pytest.raises(RuntimeError):
        UNetPPAdapter(bad_checkpoint)
