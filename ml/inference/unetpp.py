"""CPU inference adapter for the trained ResNet34 U-Net++ stenosis segmenter."""

from __future__ import annotations

import gc
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import segmentation_models_pytorch as smp
import torch
import torch.nn.functional as F
from PIL import Image, UnidentifiedImageError


INPUT_SIZE = (512, 512)  # Pillow order: width, height.
IMAGE_MEAN = 0.449
IMAGE_STD = 0.226
DEFAULT_THRESHOLD = 0.20
GRADCAM_TARGET_LAYER = "decoder.blocks.x_0_4.conv2.2"
GRADCAM_METHOD = "segmentation-targeted Grad-CAM"
DEFAULT_CHECKPOINT_PATH = Path(
    r"D:\Internship Project\Important outputs\Stenosis detection outputs"
    r"\stenosis_unetpp_training_backup\stenosis_unetpp_training"
    r"\checkpoints\best_unetpp.pt"
)


class InvalidInferenceInput(ValueError):
    """The supplied image cannot be decoded or is not an accepted input type."""


@dataclass(frozen=True)
class UNetPPResult:
    """Probability map, thresholded one-channel mask and inference metadata."""

    probability_map: np.ndarray  # float32 CHW, [0, 1].
    mask: np.ndarray  # uint8 CHW, values {0, 1}.
    metadata: dict[str, Any]


@dataclass(frozen=True)
class GradCAMResult:
    """Normalized model explanation heatmap; it is not a stenosis boundary."""

    heatmap: np.ndarray  # float32 [512, 512], normalized to [0, 1].
    metadata: dict[str, Any]


class UNetPPAdapter:
    """Load the selected U-Net++ checkpoint once and infer on CPU."""

    model_id = "unetpp_resnet34_stenosis"

    def __init__(
        self,
        checkpoint_path: str | Path = DEFAULT_CHECKPOINT_PATH,
        *,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")

        self.checkpoint_path = Path(checkpoint_path)
        if not self.checkpoint_path.is_file():
            raise FileNotFoundError(f"U-Net++ checkpoint not found: {self.checkpoint_path}")
        self.threshold = float(threshold)
        self.device = torch.device("cpu")

        checkpoint = torch.load(
            self.checkpoint_path,
            map_location=self.device,
            weights_only=True,
        )
        if not isinstance(checkpoint, Mapping):
            raise TypeError("U-Net++ checkpoint must contain a mapping")
        state_dict = checkpoint.get("model_state_dict")
        if not isinstance(state_dict, Mapping):
            raise KeyError("U-Net++ checkpoint has no model_state_dict mapping")

        self._model = smp.UnetPlusPlus(
            encoder_name="resnet34",
            encoder_weights=None,
            in_channels=1,
            classes=1,
            activation=None,
        ).to(self.device)
        # Strict loading ensures no partially initialized model is used.
        self._model.load_state_dict(state_dict, strict=True)
        self._model.eval()
        try:
            target_layer = self._model.get_submodule(GRADCAM_TARGET_LAYER)
        except (AttributeError, KeyError):
            target_layer = None
        self._gradcam_target_layer = target_layer if isinstance(target_layer, torch.nn.Module) else None
        del state_dict, checkpoint
        gc.collect()

    @staticmethod
    def preprocess(image: str | Path | Image.Image) -> torch.Tensor:
        """Return normalized float32 model input shaped [1, 1, 512, 512]."""
        try:
            if isinstance(image, (str, Path)):
                with Image.open(image) as opened:
                    gray = opened.convert("L").resize(INPUT_SIZE, Image.Resampling.BILINEAR)
            elif isinstance(image, Image.Image):
                gray = image.convert("L").resize(INPUT_SIZE, Image.Resampling.BILINEAR)
            else:
                raise InvalidInferenceInput("image must be a path or a PIL image")
            array = np.asarray(gray, dtype=np.float32) / np.float32(255.0)
            array = (array - np.float32(IMAGE_MEAN)) / np.float32(IMAGE_STD)
        except InvalidInferenceInput:
            raise
        except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise InvalidInferenceInput("image is unreadable or corrupted") from exc

        if array.shape != (INPUT_SIZE[1], INPUT_SIZE[0]) or not np.isfinite(array).all():
            raise InvalidInferenceInput("image did not produce a valid 512x512 grayscale input")
        chw = np.ascontiguousarray(array[None, :, :], dtype=np.float32)
        return torch.from_numpy(chw).unsqueeze(0)

    def predict(self, image: str | Path | Image.Image) -> UNetPPResult:
        """Run CPU inference on the original image and return probabilities and mask."""
        result, _model_input = self.predict_with_input(image)
        return result

    def predict_with_input(self, image: str | Path | Image.Image) -> tuple[UNetPPResult, torch.Tensor]:
        """Run the unchanged prediction path and also return its normalized input tensor."""
        model_input = self.preprocess(image).to(self.device)
        with torch.inference_mode():
            logits = self._model(model_input)
            expected_shape = (1, 1, INPUT_SIZE[1], INPUT_SIZE[0])
            if tuple(logits.shape) != expected_shape:
                raise RuntimeError(f"Unexpected U-Net++ output shape: {tuple(logits.shape)}")
            probabilities = torch.sigmoid(logits)
            if not bool(torch.isfinite(probabilities).all()):
                raise RuntimeError("U-Net++ produced non-finite probabilities")
            probability_map = probabilities[0].to(torch.float32).cpu().numpy()
            mask = (probabilities >= self.threshold).to(torch.uint8)[0].cpu().numpy()

        result = UNetPPResult(
            probability_map=np.ascontiguousarray(probability_map),
            mask=np.ascontiguousarray(mask),
            metadata={
                "model_id": self.model_id,
                "architecture": "segmentation_models_pytorch.UnetPlusPlus",
                "encoder": "resnet34",
                "checkpoint": self.checkpoint_path.name,
                "device": str(self.device),
                "input_size": [INPUT_SIZE[0], INPUT_SIZE[1]],
                "input_channel_format": "grayscale",
                "input_dtype": "float32",
                "input_normalization": "pixel intensity divided by 255, then (x - 0.449) / 0.226",
                "resize": "direct resize to 512x512 with bilinear interpolation",
                "probability_map_format": "float32 CHW sigmoid probabilities in [0, 1]",
                "mask_format": "uint8 CHW binary mask with values 0 or 1",
                "threshold": self.threshold,
                "threshold_is_provisional": True,
                "clinical_measurements_generated": False,
            },
        )
        return result, model_input

    def gradcam(
        self,
        image: str | Path | Image.Image,
        *,
        prediction_mask: np.ndarray | None = None,
        preprocessed_input: torch.Tensor | None = None,
    ) -> GradCAMResult:
        """Compute segmentation-targeted Grad-CAM in an explicit grad-enabled pass."""
        if torch.is_inference_mode_enabled():
            raise RuntimeError("Grad-CAM cannot run inside torch.inference_mode()")
        if self._gradcam_target_layer is None:
            raise RuntimeError(f"Grad-CAM target layer is unavailable: {GRADCAM_TARGET_LAYER}")

        captured: dict[str, torch.Tensor] = {}

        def capture_activation(_module: torch.nn.Module, _inputs: tuple[object, ...], output: object) -> None:
            if not isinstance(output, torch.Tensor) or output.ndim != 4 or output.shape[0] != 1:
                raise RuntimeError("Grad-CAM target layer must produce one 4D activation map")
            captured["activation"] = output

        hook = self._gradcam_target_layer.register_forward_hook(capture_activation)
        try:
            self._model.zero_grad(set_to_none=True)
            with torch.enable_grad():
                model_input = self.preprocess(image) if preprocessed_input is None else preprocessed_input
                if tuple(model_input.shape) != (1, 1, INPUT_SIZE[1], INPUT_SIZE[0]) or model_input.dtype != torch.float32:
                    raise ValueError("preprocessed_input must be float32 with shape [1, 1, 512, 512]")
                if torch.is_inference(model_input):
                    raise ValueError("preprocessed_input cannot be an inference tensor")
                model_input = model_input.to(self.device)
                logits = self._model(model_input)
                expected_shape = (1, 1, INPUT_SIZE[1], INPUT_SIZE[0])
                if tuple(logits.shape) != expected_shape:
                    raise RuntimeError(f"Unexpected U-Net++ output shape for Grad-CAM: {tuple(logits.shape)}")
                activation = captured.get("activation")
                if activation is None or not activation.requires_grad:
                    raise RuntimeError("Grad-CAM target activation is not connected to the output")

                if prediction_mask is None:
                    predicted = torch.sigmoid(logits) >= self.threshold
                else:
                    binary_mask = np.asarray(prediction_mask)
                    if binary_mask.shape == (1, INPUT_SIZE[1], INPUT_SIZE[0]):
                        binary_mask = binary_mask[0]
                    if binary_mask.shape != (INPUT_SIZE[1], INPUT_SIZE[0]) or not np.isin(binary_mask, (0, 1)).all():
                        raise ValueError("prediction_mask must be a binary 512x512 mask")
                    predicted = torch.from_numpy(np.ascontiguousarray(binary_mask[None, None], dtype=np.uint8)).to(self.device).bool()

                predicted_pixels = predicted[0, 0]
                selected_logits = logits[0, 0][predicted_pixels]
                target_score_fallback = selected_logits.numel() == 0
                target_score = logits.max() if target_score_fallback else selected_logits.mean()
                gradients = torch.autograd.grad(target_score, activation, retain_graph=False, create_graph=False)[0]
                if not bool(torch.isfinite(gradients).all()) or not bool(torch.isfinite(activation).all()):
                    raise RuntimeError("Grad-CAM activations or gradients are non-finite")
                channel_weights = gradients.mean(dim=(2, 3), keepdim=True)
                heatmap = torch.relu((channel_weights * activation).sum(dim=1, keepdim=True))
                heatmap = F.interpolate(
                    heatmap,
                    size=(INPUT_SIZE[1], INPUT_SIZE[0]),
                    mode="bilinear",
                    align_corners=False,
                )[0, 0]
                if not bool(torch.isfinite(heatmap).all()):
                    raise RuntimeError("Grad-CAM heatmap contains non-finite values")
                minimum, maximum = heatmap.min(), heatmap.max()
                span = maximum - minimum
                if float(span.detach()) <= torch.finfo(heatmap.dtype).eps:
                    heatmap = torch.zeros_like(heatmap)
                else:
                    heatmap = (heatmap - minimum) / span
                normalized = np.ascontiguousarray(heatmap.detach().cpu().numpy(), dtype=np.float32)
        finally:
            hook.remove()
            self._model.zero_grad(set_to_none=True)

        return GradCAMResult(
            heatmap=normalized,
            metadata={
                "available": True,
                "target_layer": GRADCAM_TARGET_LAYER,
                "method": GRADCAM_METHOD,
                "target_score": "mean logits over predicted stenosis pixels; maximum logit when the mask is empty",
                "target_score_fallback": target_score_fallback,
                "predicted_pixel_count": int(predicted_pixels.sum().item()),
                "input_size": [INPUT_SIZE[0], INPUT_SIZE[1]],
                "heatmap_format": "float32 grayscale 512x512 normalized to [0, 1]",
                "clinical_interpretation": False,
            },
        )
