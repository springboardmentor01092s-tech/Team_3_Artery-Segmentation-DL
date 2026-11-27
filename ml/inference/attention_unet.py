"""CPU inference adapter for the trained Attention U-Net artery segmenter."""

from __future__ import annotations

import gc
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image, UnidentifiedImageError

from ml.models.attention_unet import AttentionUNet


INPUT_SIZE = (256, 256)  # Pillow order: width, height.
DEFAULT_CHECKPOINT_PATH = Path(__file__).resolve().parents[1] / "checkpoints" / "best_attention_unet.pt"


class InvalidInferenceInput(ValueError):
    """The supplied image cannot be decoded or is not an accepted input type."""


@dataclass(frozen=True)
class AttentionUNetResult:
    """Binary one-channel mask and non-clinical inference metadata."""

    mask: np.ndarray  # uint8 CHW array with values in {0, 1}.
    metadata: dict[str, Any]


class AttentionUNetAdapter:
    """Load the existing checkpoint once and infer binary masks on CPU."""

    model_id = "attention_unet"

    def __init__(
        self,
        checkpoint_path: str | Path = DEFAULT_CHECKPOINT_PATH,
        *,
        threshold: float = 0.50,
    ) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")

        self.checkpoint_path = Path(checkpoint_path)
        if not self.checkpoint_path.is_file():
            raise FileNotFoundError(f"Attention U-Net checkpoint not found: {self.checkpoint_path}")
        self.threshold = float(threshold)
        self.device = torch.device("cpu")

        checkpoint = torch.load(
            self.checkpoint_path,
            map_location=self.device,
            weights_only=True,
        )
        if not isinstance(checkpoint, Mapping):
            raise TypeError("Attention U-Net checkpoint must contain a mapping")
        state_dict = checkpoint.get("model_state_dict")
        if not isinstance(state_dict, Mapping):
            raise KeyError("Attention U-Net checkpoint has no model_state_dict mapping")

        self._model = AttentionUNet(in_channels=1, out_channels=1).to(self.device)
        # Strict loading prevents silent partial or mismatched checkpoint use.
        self._model.load_state_dict(state_dict, strict=True)
        self._model.eval()

        # Training checkpoints may include optimizer state; release it after loading.
        del state_dict, checkpoint
        gc.collect()

    @staticmethod
    def preprocess(image: str | Path | Image.Image) -> torch.Tensor:
        """Match ml.dataset exactly and return float32 [1, 1, 256, 256]."""
        try:
            if isinstance(image, (str, Path)):
                with Image.open(image) as opened:
                    gray = opened.convert("L").resize(INPUT_SIZE, Image.Resampling.LANCZOS)
            elif isinstance(image, Image.Image):
                gray = image.convert("L").resize(INPUT_SIZE, Image.Resampling.LANCZOS)
            else:
                raise InvalidInferenceInput("image must be a path or a PIL image")
            array = np.asarray(gray, dtype=np.float32) / 255.0
        except InvalidInferenceInput:
            raise
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise InvalidInferenceInput("image is unreadable or corrupted") from exc

        if array.shape != (INPUT_SIZE[1], INPUT_SIZE[0]) or not np.isfinite(array).all():
            raise InvalidInferenceInput("image did not produce a valid 256x256 grayscale input")
        chw = np.ascontiguousarray(array[None, :, :], dtype=np.float32)
        return torch.from_numpy(chw).unsqueeze(0)

    def predict(self, image: str | Path | Image.Image) -> AttentionUNetResult:
        """Infer on CPU and return a binary mask without clinical measurements."""
        model_input = self.preprocess(image).to(self.device)
        with torch.inference_mode():
            logits = self._model(model_input)
            if tuple(logits.shape) != (1, 1, INPUT_SIZE[1], INPUT_SIZE[0]):
                raise RuntimeError(f"Unexpected Attention U-Net output shape: {tuple(logits.shape)}")
            probabilities = torch.sigmoid(logits)
            mask = (probabilities >= self.threshold).to(torch.uint8)[0].cpu().numpy()

        return AttentionUNetResult(
            mask=np.ascontiguousarray(mask),
            metadata={
                "model_id": self.model_id,
                "checkpoint": self.checkpoint_path.name,
                "device": str(self.device),
                "input_size": [INPUT_SIZE[0], INPUT_SIZE[1]],
                "input_channel_format": "grayscale",
                "input_dtype": "float32",
                "input_normalization": "pixel intensity divided by 255; no mean/std normalization",
                "resize": "direct resize to 256x256 with Lanczos interpolation",
                "output_format": "uint8 CHW binary mask with values 0 or 1",
                "threshold": self.threshold,
                "clinical_measurements_generated": False,
            },
        )
