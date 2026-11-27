from pathlib import Path
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
import cv2
import zipfile

# STEP 1: Load original predicted masks

INPUT_DIR = Path("/kaggle/working/generated_artery_masks")
CLEAN_DIR = Path("/kaggle/working/postprocessed_artery_masks")

ORIGINAL_ZIP = Path("/kaggle/working/generated_artery_masks.zip")
CLEAN_ZIP = Path("/kaggle/working/postprocessed_artery_masks.zip")

CLEAN_DIR.mkdir(parents=True, exist_ok=True)

mask_files = sorted(INPUT_DIR.glob("*.png"))

if len(mask_files) != 300:
    raise ValueError(
        f"Expected 300 original masks, but found {len(mask_files)}. "
        "Check the input folder before continuing."
    )

print("STEP 1: Original masks verified")
print("Number of masks:", len(mask_files))
print("Input folder:", INPUT_DIR)

# Backup original masks
with zipfile.ZipFile(
    ORIGINAL_ZIP, "w", compression=zipfile.ZIP_DEFLATED
) as zipf:
    for path in mask_files:
        zipf.write(path, arcname=path.name)

with zipfile.ZipFile(ORIGINAL_ZIP, "r") as zipf:
    assert zipf.testzip() is None
    assert len(zipf.namelist()) == 300

print("Original mask ZIP created and verified.")

# STEP 2 & 3: Remove small connected components

MIN_COMPONENT_AREA = 10


def postprocess_mask(mask, min_area=MIN_COMPONENT_AREA):

    binary = (mask > 0).astype(np.uint8)

    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )

    cleaned = np.zeros_like(binary)
    removed_components = 0

    # Skip background component 0
    for component_id in range(1, count):

        area = stats[component_id, cv2.CC_STAT_AREA]

        if area >= min_area:
            cleaned[labels == component_id] = 1
        else:
            removed_components += 1

    return cleaned * 255, removed_components


total_removed = 0
total_original_pixels = 0
total_cleaned_pixels = 0

for path in mask_files:

    original = np.array(
        Image.open(path).convert("L")
    )

    cleaned, removed = postprocess_mask(original)

    Image.fromarray(cleaned).save(CLEAN_DIR / path.name)

    total_removed += removed
    total_original_pixels += int((original > 0).sum())
    total_cleaned_pixels += int((cleaned > 0).sum())


print("\nSTEP 2 & 3: Post-processing completed")
print("Connected components removed:", total_removed)
print("Original foreground pixels:", total_original_pixels)
print("Cleaned foreground pixels:", total_cleaned_pixels)
print("Cleaned masks saved:", len(list(CLEAN_DIR.glob("*.png"))))
print("Cleaning threshold:", MIN_COMPONENT_AREA, "pixels")


# STEP 4A: Create and verify cleaned masks ZIP

clean_files = sorted(CLEAN_DIR.glob("*.png"))

if len(clean_files) != 300:
    raise RuntimeError(
        f"Expected 300 cleaned masks, found {len(clean_files)}"
    )

with zipfile.ZipFile(
    CLEAN_ZIP, "w", compression=zipfile.ZIP_DEFLATED
) as zipf:
    for path in clean_files:
        zipf.write(path, arcname=path.name)

with zipfile.ZipFile(CLEAN_ZIP, "r") as zipf:
    assert zipf.testzip() is None
    assert len(zipf.namelist()) == 300

print("\nSTEP 4: Cleaned masks ZIP verified")
print("Cleaned masks folder:", CLEAN_DIR)
print("Cleaned ZIP:", CLEAN_ZIP)
print(f"ZIP size: {CLEAN_ZIP.stat().st_size / (1024**2):.2f} MB")


# STEP 4B: Visual comparison before and after

sample_indices = [0, 10, 25, 50]

fig, axes = plt.subplots(
    len(sample_indices), 2,
    figsize=(10, 3 * len(sample_indices))
)

for row, idx in enumerate(sample_indices):

    path = mask_files[idx]

    original = np.array(
        Image.open(path).convert("L")
    )

    cleaned = np.array(
        Image.open(CLEAN_DIR / path.name).convert("L")
    )

    axes[row, 0].imshow(original, cmap="gray", vmin=0, vmax=255)
    axes[row, 0].set_title(f"Original: {path.name}")

    axes[row, 1].imshow(cleaned, cmap="gray", vmin=0, vmax=255)
    axes[row, 1].set_title("Post-processed")

    axes[row, 0].axis("off")
    axes[row, 1].axis("off")

    print(
        f"{path.name}: "
        f"original pixels={(original > 0).sum()}, "
        f"cleaned pixels={(cleaned > 0).sum()}"
    )

plt.tight_layout()
plt.show()

print("\nALL FOUR STEPS COMPLETED.")