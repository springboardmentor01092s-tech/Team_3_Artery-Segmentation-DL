
import json
import cv2
import numpy as np
from pathlib import Path

DATASET = Path(
    r"C:\Users\aksha\Downloads\arcade\syntax\train"
)
IMAGE_DIR = DATASET / "images"
JSON_PATH = DATASET / "annotations" / "train.json"
OUTPUT_DIR = DATASET / "masks"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load the annotation file
with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

# Map image IDs to image metadata
image_info = {item["id"]: item for item in data["images"]}

# Group annotations by image ID
annotations_by_image = {}
for ann in data["annotations"]:
    annotations_by_image.setdefault(
        ann["image_id"], []
    ).append(ann)

total = len(image_info)
saved = 0
missing = 0

for index, (image_id, info) in enumerate(image_info.items(), start=1):
    image_path = IMAGE_DIR / info["file_name"]

    image = cv2.imread(str(image_path))
    if image is None:
        print(f"Missing/unreadable image: {image_path}")
        missing += 1
        continue

    height, width = image.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)
    polygon_count = 0

    for ann in annotations_by_image.get(image_id, []):
        segmentation = ann.get("segmentation", [])

        # Polygon format in COCO-style annotations
        if isinstance(segmentation, list):
            for polygon in segmentation:
                if not isinstance(polygon, list) or len(polygon) < 6:
                    continue

                points = np.array(
                    polygon, dtype=np.float32
                ).reshape(-1, 2)

                points[:, 0] = np.clip(points[:, 0], 0, width - 1)
                points[:, 1] = np.clip(points[:, 1], 0, height - 1)

                points = np.round(points).astype(np.int32)
                cv2.fillPoly(mask, [points], 255)
                polygon_count += 1

    if polygon_count == 0:
        print(f"No polygon mask: {info['file_name']}")
        continue

    output_path = OUTPUT_DIR / (
        Path(info["file_name"]).stem + "_mask.png"
    )
    cv2.imwrite(str(output_path), mask)
    saved += 1

    if index % 50 == 0 or index == total:
        print(f"Progress: {index}/{total}")

print("\nMask generation finished.")
print("Images in annotation file:", total)
print("Masks saved:", saved)
print("Missing/unreadable images:", missing)
print("Output folder:", OUTPUT_DIR)
