
import json
import cv2
import numpy as np
from pathlib import Path

# Update this path to your ARCADE dataset folder
DATASET = Path(
    r"C:\Users\aksha\Downloads\arcade\syntax\train"
)

IMAGE_PATH = DATASET / "images" / "866.png"
JSON_PATH = DATASET / "annotations" / "train.json"

OUTPUT_DIR = Path("mask_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

# Load image and annotations
image = cv2.imread(str(IMAGE_PATH))
if image is None:
    raise FileNotFoundError(f"Image not found: {IMAGE_PATH}")

with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

# Find the image's internal COCO ID
image_info = next(
    (item for item in data["images"] if item["file_name"].endswith("866.png")),
    None
)

if image_info is None:
    raise ValueError("866.png was not found in the JSON images list.")

image_id = image_info["id"]
height, width = image.shape[:2]

# Create a blank mask and overlay
mask = np.zeros((height, width), dtype=np.uint8)
overlay = image.copy()
found = 0

for ann in data["annotations"]:
    if ann["image_id"] != image_id:
        continue

    # Draw polygon annotations
    for polygon in ann.get("segmentation", []):
        if isinstance(polygon, list) and len(polygon) >= 6:
            points = np.array(polygon, dtype=np.float32).reshape(-1, 2)
            points = np.round(points).astype(np.int32)
            cv2.fillPoly(mask, [points], 255)
            found += 1

if found == 0:
    raise ValueError(
        f"No polygon annotations found for image ID {image_id}."
    )

# Save binary mask and colored overlay
cv2.imwrite(str(OUTPUT_DIR / "866_mask.png"), mask)

color = np.zeros_like(image)
color[:, :, 1] = mask  # Green mask
overlay = cv2.addWeighted(image, 0.75, color, 0.65, 0)

cv2.imwrite(str(OUTPUT_DIR / "866_overlay.png"), overlay)

print("Image ID:", image_id)
print("Polygons drawn:", found)
print("Mask and overlay saved in:", OUTPUT_DIR.resolve())
