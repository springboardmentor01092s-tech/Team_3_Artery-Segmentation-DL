
from pathlib import Path
import sys
import json
import random
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

CODE_ROOT = Path("/kaggle/input/datasets/lakshyanamdev05/arcade-u-net-training-code/ml")
DATA_ROOT = Path("/kaggle/input/datasets/lakshyanamdev05/arcade-artery-segmentation-training-data/arcade/arcade")
MASK_ROOT = Path("/kaggle/input/datasets/lakshyanamdev05/arcade-artery-segmentation-training-data/arcade/arcade_prepared_masks")

OUTPUT_ROOT = Path("/kaggle/working/advanced_segmentation")
CHECKPOINT_DIR = OUTPUT_ROOT / "checkpoints"
REPORT_DIR = OUTPUT_ROOT / "reports"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(CODE_ROOT))
sys.path.insert(0, str(OUTPUT_ROOT / "models"))

from dataset import ArcadeSyntaxDataset
from attention_unet import AttentionUNet

SEED = 42
IMAGE_SIZE = (256, 256)
BATCH_SIZE = 2
EPOCHS = 30
LEARNING_RATE = 1e-4
NUM_WORKERS = 2

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Device:", device)

train_dataset = ArcadeSyntaxDataset(
    dataset_root=DATA_ROOT,
    mask_root=MASK_ROOT,
    split="train",
    image_size=IMAGE_SIZE
)
val_dataset = ArcadeSyntaxDataset(
    dataset_root=DATA_ROOT,
    mask_root=MASK_ROOT,
    split="val",
    image_size=IMAGE_SIZE
)

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=NUM_WORKERS,
    pin_memory=(device.type == "cuda")
)
val_loader = DataLoader(
    val_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=NUM_WORKERS,
    pin_memory=(device.type == "cuda")
)

class DiceLoss(nn.Module):
    def forward(self, logits, targets, smooth=1.0):
        probabilities = torch.sigmoid(logits)
        probabilities = probabilities.reshape(probabilities.size(0), -1)
        targets = targets.reshape(targets.size(0), -1)
        intersection = (probabilities * targets).sum(dim=1)
        dice = (2.0 * intersection + smooth) / (
            probabilities.sum(dim=1) + targets.sum(dim=1) + smooth
        )
        return 1.0 - dice.mean()

bce_loss = nn.BCEWithLogitsLoss()
dice_loss = DiceLoss()

def combined_loss(logits, targets):
    return 0.5 * bce_loss(logits, targets) + 0.5 * dice_loss(logits, targets)

model = AttentionUNet(in_channels=1, out_channels=1).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

best_val_dice = -1.0
history = []

print("Train images:", len(train_dataset))
print("Validation images:", len(val_dataset))
print("Batch size:", BATCH_SIZE)
print("Epochs:", EPOCHS)
print("Trainable parameters:", sum(p.numel() for p in model.parameters() if p.requires_grad))

for epoch in range(EPOCHS):
    model.train()
    train_loss_total = 0.0

    for images, masks in train_loader:
        images = images.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)
        logits = model(images)
        loss = combined_loss(logits, masks)
        loss.backward()
        optimizer.step()

        train_loss_total += loss.item() * images.size(0)

    train_loss = train_loss_total / len(train_dataset)

    model.eval()
    val_loss_total = 0.0
    dice_total = 0.0
    pixel_accuracy_total = 0.0
    image_count = 0

    with torch.no_grad():
        for images, masks in val_loader:
            images = images.to(device, non_blocking=True)
            masks = masks.to(device, non_blocking=True)

            logits = model(images)
            loss = combined_loss(logits, masks)
            probabilities = torch.sigmoid(logits)
            predictions = (probabilities >= 0.5).float()

            val_loss_total += loss.item() * images.size(0)

            pred_flat = predictions.reshape(predictions.size(0), -1)
            mask_flat = masks.reshape(masks.size(0), -1)
            intersection = (pred_flat * mask_flat).sum(dim=1)
            dice_scores = (2.0 * intersection + 1.0) / (
                pred_flat.sum(dim=1) + mask_flat.sum(dim=1) + 1.0
            )
            dice_total += dice_scores.sum().item()

            pixel_accuracy_total += (
                (predictions == masks).float().mean(dim=(1, 2, 3)).sum().item()
            )
            image_count += images.size(0)

    val_loss = val_loss_total / len(val_dataset)
    val_dice = dice_total / image_count
    val_pixel_accuracy = pixel_accuracy_total / image_count

    epoch_record = {
        "epoch": epoch + 1,
        "train_loss": train_loss,
        "val_loss": val_loss,
        "val_dice": val_dice,
        "val_pixel_accuracy": val_pixel_accuracy
    }
    history.append(epoch_record)

    print(
        f"Epoch {epoch + 1:02d}/{EPOCHS} | "
        f"Train Loss: {train_loss:.4f} | "
        f"Val Loss: {val_loss:.4f} | "
        f"Val Dice: {val_dice:.4f} | "
        f"Val Pixel Accuracy: {val_pixel_accuracy:.4f}"
    )

    if val_dice > best_val_dice:
        best_val_dice = val_dice
        torch.save(
            {
                "epoch": epoch + 1,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "best_val_dice": best_val_dice,
                "image_size": IMAGE_SIZE,
                "model_name": "AttentionUNet"
            },
            CHECKPOINT_DIR / "best_attention_unet.pt"
        )
        print("  Saved new best checkpoint.")

report = {
    "model": "Attention U-Net",
    "seed": SEED,
    "image_size": IMAGE_SIZE,
    "batch_size": BATCH_SIZE,
    "epochs_requested": EPOCHS,
    "best_validation_dice": best_val_dice,
    "history": history
}
with open(REPORT_DIR / "attention_unet_training_report.json", "w") as f:
    json.dump(report, f, indent=2)

print("\\nTraining complete.")
print("Best validation Dice:", round(best_val_dice, 4))
print("Checkpoint:", CHECKPOINT_DIR / "best_attention_unet.pt")
print("Report:", REPORT_DIR / "attention_unet_training_report.json")
