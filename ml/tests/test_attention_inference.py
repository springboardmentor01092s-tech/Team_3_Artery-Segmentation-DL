from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from ml.inference.attention_unet import (
    DEFAULT_CHECKPOINT_PATH,
    AttentionUNetAdapter,
    InvalidInferenceInput,
)


@pytest.fixture(scope="module")
def adapter():
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(min(previous_threads, 2))
    try:
        yield AttentionUNetAdapter(DEFAULT_CHECKPOINT_PATH, threshold=0.50)
    finally:
        torch.set_num_threads(previous_threads)


def test_existing_checkpoint_loads_strictly_on_cpu(adapter: AttentionUNetAdapter) -> None:
    assert adapter._model.training is False
    assert all(parameter.device.type == "cpu" for parameter in adapter._model.parameters())


def test_synthetic_image_produces_binary_one_channel_mask(adapter: AttentionUNetAdapter) -> None:
    synthetic = Image.fromarray(np.full((180, 240, 3), 127, dtype=np.uint8), mode="RGB")

    result = adapter.predict(synthetic)

    assert result.mask.shape == (1, 256, 256)
    assert result.mask.dtype == np.uint8
    assert set(np.unique(result.mask)).issubset({0, 1})
    assert result.metadata["model_id"] == "attention_unet"
    assert result.metadata["input_size"] == [256, 256]
    assert result.metadata["threshold"] == 0.50
    assert result.metadata["clinical_measurements_generated"] is False


def test_preprocessing_matches_training_input_contract() -> None:
    image = Image.fromarray(np.full((20, 40), 255, dtype=np.uint8), mode="L")

    tensor = AttentionUNetAdapter.preprocess(image)

    assert tuple(tensor.shape) == (1, 1, 256, 256)
    assert tensor.dtype == torch.float32
    assert torch.all(tensor == 1.0)


def test_corrupt_and_unsupported_inputs_are_rejected(tmp_path: Path) -> None:
    corrupt_file = tmp_path / "corrupt.png"
    corrupt_file.write_bytes(b"not a valid image")

    with pytest.raises(InvalidInferenceInput, match="unreadable or corrupted"):
        AttentionUNetAdapter.preprocess(corrupt_file)
    with pytest.raises(InvalidInferenceInput, match="path or a PIL image"):
        AttentionUNetAdapter.preprocess(object())  # type: ignore[arg-type]


def test_mismatched_checkpoint_is_rejected_strictly(tmp_path: Path) -> None:
    bad_checkpoint = tmp_path / "bad_checkpoint.pt"
    torch.save({"model_state_dict": {}}, bad_checkpoint)

    with pytest.raises(RuntimeError):
        AttentionUNetAdapter(bad_checkpoint)
