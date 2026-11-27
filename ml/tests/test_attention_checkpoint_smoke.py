from collections.abc import Mapping
import gc
from pathlib import Path
from time import perf_counter

import pytest
import torch

from ml.models.attention_unet import AttentionUNet


CHECKPOINT_PATH = Path(__file__).resolve().parents[1] / "checkpoints" / "best_attention_unet.pt"
EXPECTED_SHAPE = (1, 1, 256, 256)


def test_attention_unet_checkpoint_loads_and_runs_on_cpu():
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(min(previous_threads, 2))
    try:
        if not CHECKPOINT_PATH.is_file():
            raise FileNotFoundError(f"Attention U-Net checkpoint not found: {CHECKPOINT_PATH}")

        checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True)
        if not isinstance(checkpoint, Mapping):
            raise TypeError("Checkpoint must contain a mapping")

        checkpoint_keys = sorted(str(key) for key in checkpoint.keys())
        state_dict = checkpoint.get("model_state_dict")
        if not isinstance(state_dict, Mapping):
            raise KeyError("Checkpoint does not contain a model_state_dict mapping")

        model = AttentionUNet(in_channels=1, out_channels=1).to("cpu")
        model.load_state_dict(state_dict, strict=True)
        model.eval()

        # Release the optimizer and checkpoint metadata before allocating activations.
        del state_dict, checkpoint
        gc.collect()

        synthetic_input = torch.rand(EXPECTED_SHAPE, dtype=torch.float32, device="cpu")
        started = perf_counter()
        with torch.inference_mode():
            logits = model(synthetic_input)
        elapsed_seconds = perf_counter() - started

        assert tuple(logits.shape) == EXPECTED_SHAPE
        assert bool(torch.isfinite(logits).all())

        probabilities = torch.sigmoid(logits)
        assert bool(torch.isfinite(probabilities).all())
        assert float(probabilities.min()) >= 0.0
        assert float(probabilities.max()) <= 1.0

        binary_mask = (probabilities >= 0.50).to(torch.uint8)
        assert tuple(binary_mask.shape) == EXPECTED_SHAPE
        assert set(torch.unique(binary_mask).tolist()).issubset({0, 1})

        print(
            "PASS Attention U-Net checkpoint CPU smoke | "
            f"checkpoint_keys={checkpoint_keys} | strict_load=True | "
            f"device=cpu | output_shape={tuple(logits.shape)} | "
            f"inference_time={elapsed_seconds:.3f}s"
        )
    except Exception as exc:
        print(f"FAIL Attention U-Net checkpoint CPU smoke | {type(exc).__name__}: {exc}")
        raise
    finally:
        torch.set_num_threads(previous_threads)
