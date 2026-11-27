from pathlib import Path
import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
import zipfile

# STEP 1: Configure paths

INPUT_DIR = Path("/kaggle/working/postprocessed_artery_masks")

OUTPUT_DIR = Path("/kaggle/working/vessel_structure_analysis")

LABEL_DIR = OUTPUT_DIR / "labeled_components"
OVERLAY_DIR = OUTPUT_DIR / "visualizations"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LABEL_DIR.mkdir(parents=True, exist_ok=True)
OVERLAY_DIR.mkdir(parents=True, exist_ok=True)

mask_files = sorted(INPUT_DIR.glob("*.png"))

if len(mask_files) != 300:
    raise ValueError(
        f"Expected 300 post-processed masks, found {len(mask_files)}"
    )

print("STEP 1: Loaded", len(mask_files), "cleaned artery masks")


# STEP 2: Identify connected vessel components

all_records = []
summary_records = []

for mask_path in mask_files:

    mask = np.array(
        Image.open(mask_path).convert("L")
    )

    binary = (mask > 0).astype(np.uint8)

    num_labels, labels, stats, centroids = (
        cv2.connectedComponentsWithStats(
            binary, connectivity=8
        )
    )

    component_count = num_labels - 1

    summary_records.append({
        "image_name": mask_path.name,
        "component_count": component_count,
        "foreground_pixels": int(binary.sum())
    })

    colored = np.zeros(
        (*binary.shape, 3), dtype=np.uint8
    )

    for component_id in range(1, num_labels):

        x = int(stats[component_id, cv2.CC_STAT_LEFT])
        y = int(stats[component_id, cv2.CC_STAT_TOP])
        w = int(stats[component_id, cv2.CC_STAT_WIDTH])
        h = int(stats[component_id, cv2.CC_STAT_HEIGHT])
        area = int(stats[component_id, cv2.CC_STAT_AREA])

        cx, cy = centroids[component_id]

        all_records.append({
            "image_name": mask_path.name,
            "component_id": component_id,
            "area_pixels": area,
            "bbox_x": x,
            "bbox_y": y,
            "bbox_width": w,
            "bbox_height": h,
            "centroid_x": round(float(cx), 2),
            "centroid_y": round(float(cy), 2)
        })

        color = (
            (component_id * 67) % 256,
            (component_id * 131) % 256,
            (component_id * 197) % 256
        )

        colored[labels == component_id] = color

    # Save component visualization
    Image.fromarray(colored).save(
        LABEL_DIR / f"{mask_path.stem}_components.png"
    )

    # Create overlay visualization
    gray_rgb = np.repeat(
        (binary * 100)[:, :, None], 3, axis=2
    )

    overlay = np.where(
        colored.sum(axis=2, keepdims=True) > 0,
        colored,
        gray_rgb
    )

    Image.fromarray(overlay).save(
        OVERLAY_DIR / f"{mask_path.stem}_overlay.png"
    )


# STEP 3: Save component statistics as CSV reports

components_df = pd.DataFrame(all_records)
summary_df = pd.DataFrame(summary_records)

components_csv = OUTPUT_DIR / "vessel_component_details.csv"
summary_csv = OUTPUT_DIR / "vessel_structure_summary.csv"

components_df.to_csv(components_csv, index=False)
summary_df.to_csv(summary_csv, index=False)

total_components = int(
    summary_df["component_count"].sum()
)

print("\nSTEP 2: Connected-component analysis completed")
print("Images analyzed:", len(summary_df))
print("Total connected components:", total_components)

print(
    "Images with no foreground components:",
    int((summary_df["component_count"] == 0).sum())
)

print("\nSTEP 3: Reports saved")
print(components_csv)
print(summary_csv)

print("\nFirst 10 component records:")
print(components_df.head(10).to_string(index=False))


# STEP 4: Visualize examples

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

    component_image = np.array(
        Image.open(
            LABEL_DIR / f"{path.stem}_components.png"
        )
    )

    axes[row, 0].imshow(original, cmap="gray")
    axes[row, 0].set_title(f"Cleaned mask: {path.name}")

    axes[row, 1].imshow(component_image)
    axes[row, 1].set_title("Connected components")

    axes[row, 0].axis("off")
    axes[row, 1].axis("off")

plt.tight_layout()
plt.show()


# ZIP all reports, component images and visualizations

ZIP_PATH = Path(
    "/kaggle/working/vessel_structure_analysis.zip"
)

with zipfile.ZipFile(
    ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED
) as zipf:

    for path in OUTPUT_DIR.rglob("*"):
        if path.is_file():
            zipf.write(
                path,
                arcname=str(path.relative_to(OUTPUT_DIR))
            )

with zipfile.ZipFile(ZIP_PATH, "r") as zipf:
    assert zipf.testzip() is None

print("\nVESSEL STRUCTURE EXTRACTION COMPLETED")
print("Images analyzed:", len(summary_df))
print("Total connected components:", total_components)
print("Component details:", components_csv)
print("Per-image summary:", summary_csv)
print("Output ZIP:", ZIP_PATH)
print(
    f"ZIP size: {ZIP_PATH.stat().st_size / (1024**2):.2f} MB"
)