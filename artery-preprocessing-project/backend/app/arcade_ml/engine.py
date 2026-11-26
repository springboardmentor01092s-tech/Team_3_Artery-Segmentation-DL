from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import DataLoader

from .dataset import ArcadeSegDataset
from .losses import BCEDiceLoss, TverskyLoss
from .metrics import hard_metrics
from .models import build_model, count_parameters, detect_architecture
from .normalization import normalize_rgb_array
from .paths import checkpoints_dir


def get_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def unused_checkpoint_path(path: Path) -> Path:
    """Choose a new checkpoint filename so a training run never replaces an existing file."""
    if not path.exists():
        return path
    index = 1
    while True:
        candidate = path.with_name(f"{path.stem}_run{index:02d}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def make_loader(
    task: str,
    split: str,
    image_size: int,
    batch_size: int,
    augment: bool,
    max_samples: int | None,
    shuffle: bool,
    num_workers: int = 0,
) -> DataLoader:
    data = ArcadeSegDataset(
        task=task,
        split=split,
        image_size=image_size,
        augment=augment,
        max_samples=max_samples,
    )
    return DataLoader(
        data,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
    )


def build_loss(name: str, pos_weight: float):
    key = name.lower()
    if key == "tversky":
        return TverskyLoss()
    return BCEDiceLoss(pos_weight=pos_weight)


def train_model(args) -> dict:
    from tqdm import tqdm

    device = get_device()
    if args.split_test_forbidden and getattr(args, "use_test", False):
        raise ValueError("Test split cannot be used for training or threshold selection.")
    model = build_model(args.model, base=args.base_channels).to(device)
    criterion = build_loss(args.loss, args.pos_weight)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=0.5,
        patience=max(1, int(args.patience) // 2),
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda" and args.amp)
    train_loader = make_loader(
        args.task, "train", args.image_size, args.batch_size, True, args.max_train, True
    )
    excluded_duplicates = list(getattr(train_loader.dataset, "excluded_duplicates", []))
    if excluded_duplicates:
        print(
            f"Excluded {len(excluded_duplicates)} training image(s) with exact content duplicates "
            "in validation/test splits: " + ", ".join(excluded_duplicates[:10])
        )
    val_loader = make_loader(
        args.task, "val", args.image_size, args.batch_size, False, args.max_val, False
    )
    history = []
    best_dice = -1.0
    checkpoints_dir().mkdir(parents=True, exist_ok=True)
    out_path = unused_checkpoint_path(Path(args.output))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    patience = args.patience
    stale = 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        train_losses = []
        for images, masks, _names in tqdm(train_loader, desc=f"train {epoch}", leave=False):
            images = images.to(device)
            masks = masks.to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=scaler.is_enabled()):
                logits = model(images)
                loss = criterion(logits, masks)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            train_losses.append(float(loss.item()))

        val_stats = evaluate_loader(model, val_loader, device, threshold=0.5)
        scheduler.step(val_stats["dice"])
        row = {
            "epoch": epoch,
            "train_loss": float(np.mean(train_losses) if train_losses else 0.0),
            "lr": float(optimizer.param_groups[0]["lr"]),
            **{f"val_{k}": v for k, v in val_stats.items() if k in {"dice", "iou", "precision", "recall"}},
        }
        history.append(row)
        print(row)
        if val_stats["dice"] > best_dice:
            best_dice = val_stats["dice"]
            stale = 0
            payload = {
                "model_name": args.model,
                "task": args.task,
                "image_size": args.image_size,
                "base_channels": args.base_channels,
                "in_channels": 3,
                "out_channels": 1,
                "threshold": 0.5,
                "best_val_dice": best_dice,
                "epoch": epoch,
                "history": history,
                "excluded_cross_split_duplicates": excluded_duplicates,
                "parameters": count_parameters(model),
                "state_dict": model.state_dict(),
            }
            torch.save(payload, out_path)
        else:
            stale += 1
            if stale >= patience:
                print(f"Early stopping at epoch {epoch}")
                break

    history_path = out_path.with_suffix(".history.json")
    history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return {
        "checkpoint": str(out_path),
        "best_val_dice": best_dice,
        "history": history,
        "device": str(device),
        "excluded_cross_split_duplicates": excluded_duplicates,
    }


@torch.no_grad()
def evaluate_loader(model, loader, device, threshold: float = 0.5) -> dict:
    model.eval()
    metrics_acc = []
    for images, masks, _names in loader:
        images = images.to(device)
        masks = masks.to(device)
        logits = model(images)
        metrics_acc.append(hard_metrics(logits, masks, threshold=threshold))
    if not metrics_acc:
        return {"dice": 0.0, "iou": 0.0, "precision": 0.0, "recall": 0.0, "tp": 0, "fp": 0, "fn": 0, "tn": 0}
    keys = metrics_acc[0].keys()
    return {k: float(np.mean([m[k] for m in metrics_acc])) for k in keys}


def _extract_state_dict(blob) -> tuple[dict, dict]:
    if not isinstance(blob, dict):
        raise ValueError("Checkpoint is not a dictionary.")
    if "model_state_dict" in blob and isinstance(blob["model_state_dict"], dict):
        return blob["model_state_dict"], blob
    if "state_dict" in blob and isinstance(blob["state_dict"], dict):
        sample_key = next(iter(blob["state_dict"].keys()), "")
        if "." in str(sample_key):
            return blob["state_dict"], blob
    if any("." in str(k) for k in blob.keys()):
        return blob, {}
    raise ValueError("Could not find a model state_dict in the checkpoint.")


def load_checkpoint(path: Path, device: torch.device | None = None) -> tuple[torch.nn.Module, dict]:
    device = device or get_device()
    blob = torch.load(path, map_location=device, weights_only=False)
    state, meta = _extract_state_dict(blob)
    name = detect_architecture(state, meta if isinstance(meta, dict) else {})
    expected_smp_version = meta.get("smp_version") if isinstance(meta, dict) else None
    if name.startswith("smp_") and expected_smp_version:
        try:
            import segmentation_models_pytorch as smp
        except ImportError as exc:
            raise RuntimeError(
                "This checkpoint requires segmentation-models-pytorch. Install backend/requirements-ml.txt."
            ) from exc
        if smp.__version__ != expected_smp_version:
            raise RuntimeError(
                f"Checkpoint was trained with segmentation-models-pytorch {expected_smp_version}; "
                f"installed version is {smp.__version__}. Install the matching optional ML requirements."
            )
    model = build_model(
        name,
        in_channels=int(meta.get("in_channels", 3)) if isinstance(meta, dict) else 3,
        out_channels=int(meta.get("out_channels", 1)) if isinstance(meta, dict) else 1,
        base=int(meta.get("base_channels", 32)) if isinstance(meta, dict) else 32,
        encoder_name=meta.get("encoder_name") if isinstance(meta, dict) else None,
        encoder_weights=None,
    )
    model.load_state_dict(state)
    model.to(device)
    model.eval()
    info = dict(meta) if isinstance(meta, dict) else {}
    info["resolved_architecture"] = name
    info["checkpoint_path"] = str(path)
    return model, info


@torch.no_grad()
def predict_image(model, image_rgb: np.ndarray, image_size: int, device: torch.device,
                  normalization: str = "none") -> np.ndarray:
    h, w = image_rgb.shape[:2]
    # Match ArcadeSegDataset exactly: RGB byte image, PIL bilinear resize, /255 scaling.
    resized = Image.fromarray(image_rgb.astype(np.uint8), mode="RGB").resize(
        (image_size, image_size), Image.Resampling.BILINEAR
    )
    image_array = normalize_rgb_array(np.asarray(resized, dtype=np.float32) / 255.0, normalization)
    tensor = torch.from_numpy(image_array).permute(2, 0, 1).unsqueeze(0)
    tensor = tensor.to(device)
    logits = model(tensor)
    prob = torch.sigmoid(logits)[0, 0].cpu().numpy()
    prob = cv2_resize(prob, (w, h))
    return prob


def _metric_number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def summarize_checkpoint(path: Path) -> dict:
    """Read architecture and stored metrics without treating missing scores as zero."""
    device = torch.device("cpu")
    blob = torch.load(path, map_location=device, weights_only=False)
    state, meta = _extract_state_dict(blob)
    meta = meta if isinstance(meta, dict) else {}
    name = detect_architecture(state, meta)
    dice = _metric_number(meta.get("val_dice") if meta.get("val_dice") is not None else meta.get("best_val_dice"))
    iou = _metric_number(meta.get("val_iou"))
    precision = _metric_number(meta.get("val_precision") if meta.get("val_precision") is not None else meta.get("precision"))
    recall = _metric_number(meta.get("val_recall") if meta.get("val_recall") is not None else meta.get("recall"))
    return {
        "name": path.name,
        "checkpoint": str(path),
        "kind": "checkpoint",
        "metric_origin": "stored_in_checkpoint",
        "recomputed_here": False,
        "resolved_architecture": name,
        "stored_architecture": meta.get("architecture") or meta.get("model_name"),
        "image_size": meta.get("image_size"),
        "epoch": meta.get("epoch"),
        "task": meta.get("task"),
        "dice": dice,
        "iou": iou,
        "precision": precision,
        "recall": recall,
        "note": "Precision and recall are omitted when the checkpoint file does not store them.",
    }


def cv2_resize(arr: np.ndarray, size_wh: tuple[int, int]) -> np.ndarray:
    import cv2

    return cv2.resize(arr, size_wh, interpolation=cv2.INTER_LINEAR)
