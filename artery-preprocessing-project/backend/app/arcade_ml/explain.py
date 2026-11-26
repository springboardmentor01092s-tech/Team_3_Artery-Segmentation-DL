from __future__ import annotations

import cv2
import numpy as np
import torch
from PIL import Image

from .normalization import normalize_rgb_array


def overlay_mask(image_bgr: np.ndarray, mask: np.ndarray, color=(0, 70, 255), alpha: float = 0.45) -> np.ndarray:
    base = image_bgr.copy()
    if base.ndim == 2:
        base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    color_layer = np.zeros_like(base)
    color_layer[:, :] = color
    selected = mask > 0
    blended = cv2.addWeighted(base, 1.0, color_layer, alpha, 0)
    base[selected] = blended[selected]
    return base


def probability_heatmap(image_bgr: np.ndarray, probability: np.ndarray, alpha: float = 0.5) -> np.ndarray:
    base = image_bgr.copy()
    if base.ndim == 2:
        base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    heat = (np.clip(probability, 0, 1) * 255).astype(np.uint8)
    color = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
    return cv2.addWeighted(base, 1 - alpha, color, alpha, 0)


def draw_boxes(image_bgr: np.ndarray, boxes: list[dict], color=(40, 200, 90), label_key: str = "mean_predicted_probability") -> np.ndarray:
    canvas = image_bgr.copy()
    if canvas.ndim == 2:
        canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)
    for box in boxes:
        x, y, w, h = int(box["x"]), int(box["y"]), int(box["width"]), int(box["height"])
        cv2.rectangle(canvas, (x, y), (x + w, y + h), color, 2)
        conf = box.get(label_key)
        text = f"id={box.get('id', '?')}"
        if conf is not None:
            text += f" p={conf:.2f}"
        cv2.putText(canvas, text, (x, max(12, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)
    return canvas


def comparison_strip(image_bgr: np.ndarray, prediction: np.ndarray, ground_truth: np.ndarray | None = None) -> np.ndarray:
    """Original, predicted overlay, and optional ground-truth overlay. Not Grad-CAM."""
    original = image_bgr if image_bgr.ndim == 3 else cv2.cvtColor(image_bgr, cv2.COLOR_GRAY2BGR)
    panels = [original, overlay_mask(original, prediction, color=(0, 70, 255))]
    if ground_truth is not None:
        panels.append(overlay_mask(original, ground_truth, color=(0, 180, 70)))
    return np.concatenate(panels, axis=1)


def encode_png(image_bgr: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", image_bgr)
    if not ok:
        raise RuntimeError("Failed to encode PNG")
    return buf.tobytes()


def integrated_gradients_attribution(
    model: torch.nn.Module,
    image_rgb: np.ndarray,
    image_size: int,
    device: torch.device,
    normalization: str = "none",
    threshold: float = 0.5,
    steps: int = 16,
) -> tuple[np.ndarray, dict]:
    """Return an input attribution map for the model's predicted foreground.

    The all-zero baseline is black for unnormalized inputs and the ImageNet mean
    color for ImageNet-normalized inputs. This explains model sensitivity only;
    it is not a calibrated confidence or clinical explanation.
    """
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3 or image_rgb.size == 0:
        raise ValueError("Expected a non-empty RGB image.")
    if image_size < 1 or not 0 < threshold < 1 or steps < 2:
        raise ValueError("Invalid image size, threshold, or integration step count.")
    resized = np.asarray(Image.fromarray(image_rgb.astype(np.uint8)).resize(
        (image_size, image_size), Image.Resampling.BILINEAR
    ), dtype=np.float32) / 255.0
    normalized = normalize_rgb_array(resized, normalization)
    image = torch.from_numpy(normalized.transpose(2, 0, 1).copy()).unsqueeze(0).to(device)
    baseline = torch.zeros_like(image)

    model.eval()
    with torch.no_grad():
        logits = model(image)
    if logits.ndim != 4 or logits.shape[0] != 1:
        raise ValueError("Segmentation model must return one [1, 1, H, W] logit tensor.")
    selected = torch.sigmoid(logits.detach()) >= threshold
    if not bool(selected.any()):
        raise ValueError("The model predicted no foreground pixels at the selected threshold.")

    gradients = []
    for alpha in torch.linspace(1.0 / steps, 1.0, steps, device=device):
        point = (baseline + alpha * (image - baseline)).detach().requires_grad_(True)
        output = model(point)
        if output.shape != logits.shape:
            raise ValueError("Segmentation model output shape changed during attribution.")
        score = output[selected].mean()
        gradient, = torch.autograd.grad(score, point, retain_graph=False, create_graph=False)
        gradients.append(gradient.detach())
    attribution = (image - baseline) * torch.stack(gradients).mean(dim=0)
    heat = attribution.abs().sum(dim=1)[0].cpu().numpy()
    heat = cv2.resize(heat, (image_rgb.shape[1], image_rgb.shape[0]), interpolation=cv2.INTER_LINEAR)
    maximum = float(heat.max()) if heat.size else 0.0
    if not np.isfinite(maximum) or maximum <= 1e-12:
        raise ValueError("The model produced no finite, non-zero input attribution.")
    heat = np.clip(heat / maximum, 0, 1).astype(np.float32)
    return heat, {
        "method": "integrated_gradients",
        "target": "mean lesion logit over predicted foreground pixels",
        "steps": steps,
        "baseline": "zero normalized input (black, or ImageNet mean color)",
        "normalization": normalization,
        "threshold": float(threshold),
        "interpretation": "Relative input attribution; not clinical confidence, probability, or validated diagnostic evidence.",
    }


def attribution_heatmap(image_bgr: np.ndarray, attribution: np.ndarray, alpha: float = 0.5) -> np.ndarray:
    base = image_bgr.copy()
    if base.ndim == 2:
        base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    heat = (np.clip(attribution, 0, 1) * 255).astype(np.uint8)
    color = cv2.applyColorMap(heat, cv2.COLORMAP_TURBO)
    return cv2.addWeighted(base, 1 - alpha, color, alpha, 0)
