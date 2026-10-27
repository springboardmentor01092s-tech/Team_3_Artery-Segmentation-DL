"""Train the baseline binary U-Net using only ARCADE syntax train/val splits."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset

from ml.dataset import ArcadeSyntaxDataset
from ml.models.unet import UNet


DEFAULT_DATASET_ROOT = Path(r"C:\Users\namde\Downloads\arcade\arcade")
DEFAULT_MASK_ROOT = Path(r"C:\Users\namde\Downloads\arcade\arcade_prepared_masks")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train baseline U-Net on ARCADE syntax train and validation splits.")
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT, help="Root containing syntax/train|val|test/images")
    parser.add_argument("--mask-root", type=Path, default=DEFAULT_MASK_ROOT, help="Root containing syntax/train|val|test/masks")
    parser.add_argument("--epochs", type=int, default=30, help="Number of training epochs (default: 30)")
    parser.add_argument("--batch-size", type=int, default=2, help="Mini-batch size; default 2 keeps memory use modest")
    parser.add_argument("--image-size", type=int, default=256, help="Square input resolution; must be divisible by 16 (default: 256)")
    parser.add_argument("--cpu-threads", type=int, default=4, help="PyTorch CPU compute/inter-op thread limit (default: 4)")
    parser.add_argument("--log-every", type=int, default=10, help="Print batch progress every N batches, plus first and last (default: 10)")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent, help="Directory containing checkpoints/ and reports/")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible initialization and shuffling")
    parser.add_argument("--limit-train-samples", type=int, default=None, help="Optional training sample limit for smoke checks")
    parser.add_argument("--limit-val-samples", type=int, default=None, help="Optional validation sample limit for smoke checks")
    args = parser.parse_args()
    for argument in ("epochs", "batch_size", "cpu_threads", "log_every"):
        if getattr(args, argument) <= 0:
            parser.error(f"--{argument.replace('_', '-')} must be positive")
    for argument in ("limit_train_samples", "limit_val_samples"):
        value = getattr(args, argument)
        if value is not None and value <= 0:
            parser.error(f"--{argument.replace('_', '-')} must be positive when supplied")
    if args.image_size < 16 or args.image_size % 16 != 0:
        parser.error("--image-size must be at least 16 and divisible by 16 for the existing U-Net")
    return args


def set_reproducible_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def configure_cpu_threads(thread_count: int) -> tuple[int, int]:
    """Limit PyTorch thread pools to reduce CPU oversubscription."""
    torch.set_num_threads(thread_count)
    try:
        torch.set_num_interop_threads(min(thread_count, 4))
    except RuntimeError:
        # PyTorch only permits changing inter-op threads before its pool starts.
        pass
    return torch.get_num_threads(), torch.get_num_interop_threads()


def dice_loss_from_logits(logits: torch.Tensor, targets: torch.Tensor, smooth: float = 1.0) -> torch.Tensor:
    probabilities = torch.sigmoid(logits)
    probabilities = probabilities.reshape(probabilities.shape[0], -1)
    targets = targets.reshape(targets.shape[0], -1)
    intersection = (probabilities * targets).sum(dim=1)
    dice = (2.0 * intersection + smooth) / (probabilities.sum(dim=1) + targets.sum(dim=1) + smooth)
    return 1.0 - dice.mean()


def combined_segmentation_loss(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    bce = F.binary_cross_entropy_with_logits(logits, targets)
    dice = dice_loss_from_logits(logits, targets)
    return 0.5 * bce + 0.5 * dice


def mean_binary_dice(logits: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5, smooth: float = 1.0) -> torch.Tensor:
    predictions = (torch.sigmoid(logits) >= threshold).to(targets.dtype).reshape(targets.shape[0], -1)
    targets = targets.reshape(targets.shape[0], -1)
    intersection = (predictions * targets).sum(dim=1)
    dice = (2.0 * intersection + smooth) / (predictions.sum(dim=1) + targets.sum(dim=1) + smooth)
    return dice.mean()


def make_loader(dataset, batch_size: int, *, shuffle: bool, seed: int, device: torch.device) -> DataLoader:
    generator = torch.Generator().manual_seed(seed) if shuffle else None
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=0,
        pin_memory=device.type == "cuda",
        generator=generator,
    )


def select_subset(dataset, limit: int | None):
    if limit is None:
        return dataset
    return Subset(dataset, range(min(limit, len(dataset))))


def run_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    *,
    epoch: int,
    total_epochs: int,
    phase: str,
    log_every: int,
    optimizer=None,
) -> dict[str, float]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    total_dice = 0.0
    examples = 0
    total_batches = len(loader)
    for batch_index, (images, masks) in enumerate(loader, start=1):
        should_log = batch_index == 1 or batch_index % log_every == 0 or batch_index == total_batches
        if should_log:
            print(f"Epoch {epoch}/{total_epochs} | {phase} batch {batch_index}/{total_batches} starting", flush=True)
        images = images.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)
        if training:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(training):
            logits = model(images)
            loss = combined_segmentation_loss(logits, masks)
            if training:
                loss.backward()
                optimizer.step()
        batch_size = images.shape[0]
        total_loss += loss.detach().item() * batch_size
        total_dice += mean_binary_dice(logits.detach(), masks).item() * batch_size
        examples += batch_size
        if should_log:
            print(
                f"Epoch {epoch}/{total_epochs} | {phase} batch {batch_index}/{total_batches} "
                f"complete - loss={loss.detach().item():.4f}",
                flush=True,
            )
    if examples == 0:
        raise ValueError("The selected dataset split has no samples")
    return {"loss": total_loss / examples, "dice": total_dice / examples}


def save_report(report_path: Path, report: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def train(args: argparse.Namespace) -> dict[str, Any]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cpu_thread_settings = configure_cpu_threads(args.cpu_threads) if device.type == "cpu" else None
    set_reproducible_seed(args.seed)

    image_size = (args.image_size, args.image_size)
    train_dataset = ArcadeSyntaxDataset(args.dataset_root, args.mask_root, "train", image_size=image_size)
    validation_dataset = ArcadeSyntaxDataset(args.dataset_root, args.mask_root, "val", image_size=image_size)
    train_dataset = select_subset(train_dataset, args.limit_train_samples)
    validation_dataset = select_subset(validation_dataset, args.limit_val_samples)
    if len(train_dataset) == 0 or len(validation_dataset) == 0:
        raise ValueError("Both the training and validation splits must contain at least one sample")

    train_loader = make_loader(train_dataset, args.batch_size, shuffle=True, seed=args.seed, device=device)
    validation_loader = make_loader(validation_dataset, args.batch_size, shuffle=False, seed=args.seed, device=device)
    model = UNet(in_channels=1, out_channels=1).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)

    checkpoint_directory = args.output_dir / "checkpoints"
    report_path = args.output_dir / "reports" / "baseline_training_report.json"
    checkpoint_directory.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_directory / "best_unet.pt"
    best_validation_dice = -1.0
    best_epoch = 0
    history: list[dict[str, float | int]] = []
    report: dict[str, Any] = {
        "model": "UNet(in_channels=1, out_channels=1)",
        "dataset": "ARCADE syntax",
        "training_split": "train",
        "selection_split": "val",
        "test_split_used": False,
        "input_size": list(image_size),
        "loss": "0.5 * BCEWithLogitsLoss + 0.5 * DiceLoss",
        "optimizer": "Adam(lr=0.0001)",
        "seed": args.seed,
        "device": str(device),
        "epochs_requested": args.epochs,
        "batch_size": args.batch_size,
        "cpu_threads_requested": args.cpu_threads if device.type == "cpu" else None,
        "cpu_threads_configured": cpu_thread_settings[0] if cpu_thread_settings else None,
        "cpu_interop_threads_configured": cpu_thread_settings[1] if cpu_thread_settings else None,
        "log_every_batches": args.log_every,
        "training_samples": len(train_dataset),
        "validation_samples": len(validation_dataset),
        "history": history,
        "best_epoch": None,
        "best_validation_dice": None,
        "checkpoint": str(checkpoint_path),
        "clinical_validation_claim": False,
    }

    print(
        f"Device={device}; input_size={args.image_size}x{args.image_size}; batch_size={args.batch_size}; "
        f"train_samples={len(train_dataset)}; val_samples={len(validation_dataset)}"
        + (f"; torch_threads={cpu_thread_settings[0]}; interop_threads={cpu_thread_settings[1]}" if cpu_thread_settings else ""),
        flush=True,
    )

    for epoch in range(1, args.epochs + 1):
        train_metrics = run_epoch(
            model,
            train_loader,
            device,
            epoch=epoch,
            total_epochs=args.epochs,
            phase="train",
            log_every=args.log_every,
            optimizer=optimizer,
        )
        with torch.no_grad():
            validation_metrics = run_epoch(
                model,
                validation_loader,
                device,
                epoch=epoch,
                total_epochs=args.epochs,
                phase="validation",
                log_every=args.log_every,
            )
        row = {
            "epoch": epoch,
            "training_loss": train_metrics["loss"],
            "validation_loss": validation_metrics["loss"],
            "validation_dice": validation_metrics["dice"],
        }
        history.append(row)
        if validation_metrics["dice"] > best_validation_dice:
            best_validation_dice = validation_metrics["dice"]
            best_epoch = epoch
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "model": "UNet(in_channels=1, out_channels=1)",
                    "epoch": epoch,
                    "validation_dice": best_validation_dice,
                    "seed": args.seed,
                    "input_size": list(image_size),
                    "threshold": 0.5,
                },
                checkpoint_path,
            )
        report["best_epoch"] = best_epoch
        report["best_validation_dice"] = best_validation_dice
        save_report(report_path, report)
        print(
            f"Epoch {epoch}/{args.epochs}: train_loss={train_metrics['loss']:.4f} "
            f"val_loss={validation_metrics['loss']:.4f} val_dice={validation_metrics['dice']:.4f}"
        )

    print(f"Best validation Dice: {best_validation_dice:.4f} (epoch {best_epoch})")
    print(f"Checkpoint: {checkpoint_path}")
    print(f"Report: {report_path}")
    return report


if __name__ == "__main__":
    train(parse_args())
