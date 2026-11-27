from pathlib import Path
import sys
import torch
import numpy as np
from PIL import Image
from torch.utils.data import DataLoader
import matplotlib.pyplot as plt

# Paths
CODE_ROOT = Path(
    "/kaggle/input/datasets/lakshyanamdev05/"
    "arcade-u-net-training-code/ml"
)
DATA_ROOT = Path(
    "/kaggle/input/datasets/lakshyanamdev05/"
    "arcade-artery-segmentation-training-data/arcade/arcade"
)
MASK_ROOT = Path(
    "/kaggle/input/datasets/lakshyanamdev05/"
    "arcade-artery-segmentation-training-data/arcade/arcade_prepared_masks"
)
MODEL_DIR = Path(
    "/kaggle/working/advanced_segmentation/models"
)
CHECKPOINT = Path(
    "/kaggle/working/advanced_segmentation/checkpoints/"
    "best_attention_unet.pt"
)

OUTPUT_DIR = Path("/kaggle/working/generated_artery_masks")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(CODE_ROOT))
sys.path.insert(0, str(MODEL_DIR))

from dataset import ArcadeSyntaxDataset
from attention_unet import AttentionUNet

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Load trained model
model = AttentionUNet(in_channels=1, out_channels=1).to(device)

checkpoint = torch.load(
    CHECKPOINT, map_location=device, weights_only=True
)

model.load_state_dict(checkpoint["model_state_dict"])
model.eval()

# Load test images
dataset = ArcadeSyntaxDataset(
    dataset_root=DATA_ROOT,
    mask_root=MASK_ROOT,
    split="test",
    image_size=(256, 256)
)

loader = DataLoader(
    dataset, batch_size=1, shuffle=False, num_workers=2
)

total_masks = 0

with torch.no_grad():
    for idx, (images, _) in enumerate(loader):
        images = images.to(device)

        probabilities = torch.sigmoid(model(images))
        predictions = (probabilities >= 0.5).cpu().numpy()

        mask = (predictions[0, 0] * 255).astype(np.uint8)
        filename = f"artery_mask_{idx:04d}.png"

        Image.fromarray(mask).save(OUTPUT_DIR / filename)
        total_masks += 1

print("Artery mask generation completed!")
print("Test images processed:", len(dataset))
print("Masks saved:", total_masks)
print("Output folder:", OUTPUT_DIR)
print("Example file:", OUTPUT_DIR / "artery_mask_0000.png")

# Verify generated masks
mask_files = sorted(OUTPUT_DIR.glob("*.png"))

print("Number of generated masks:", len(mask_files))

if not mask_files:
    raise RuntimeError("No masks were generated.")

sample_files = [
    mask_files[i] for i in [0, 10, 25, 50]
    if i < len(mask_files)
]

fig, axes = plt.subplots(
    1, len(sample_files),
    figsize=(4 * len(sample_files), 4)
)

if len(sample_files) == 1:
    axes = [axes]

for ax, path in zip(axes, sample_files):
    mask = np.array(Image.open(path))

    ax.imshow(mask, cmap="gray", vmin=0, vmax=255)
    ax.set_title(path.name)
    ax.axis("off")

    print(
        path.name,
        "| dimensions:", mask.shape,
        "| foreground pixels:", int((mask > 0).sum())
    )

plt.tight_layout()
plt.show()