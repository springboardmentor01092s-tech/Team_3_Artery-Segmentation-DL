
import json
from pathlib import Path

import cv2
import numpy as np

base = Path(r"C:\Users\aksha\Downloads\arcade\syntax")

for split in ["val", "test"]:
    split_dir = base / split
    images_dir = split_dir / "images"
    annotations_dir = split_dir / "annotations"
    json_path = annotations_dir / f"{split}.json"
    output_dir = split_dir / "masks"

    if not json_path.exists():
        print(f"Annotation file not found: {json_path}")
        continue

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    image_map = {img["id"]: img for img in data["images"]}
    annotations_by_image = {}

    for ann in data["annotations"]:
        annotations_by_image.setdefault(
            ann["image_id"], []
        ).append(ann)

    output_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    missing = 0

    for image_id, info in image_map.items():
        image_path = images_dir / info["file_name"]
        image = cv2.imread(str(image_path))

        if image is None:
            print("Could not read:", image_path)
            missing += 1
            continue

        height, width = image.shape[:2]
        mask = np.zeros((height, width), dtype=np.uint8)

        for ann in annotations_by_image.get(image_id, []):
            for polygon in ann.get("segmentation", []):
                points = np.asarray(
                    polygon, dtype=np.float32
                ).reshape(-1, 2)

                points = np.round(points).astype(np.int32)

                if len(points) >= 3:
                    cv2.fillPoly(mask, [points], 255)

        output_path = output_dir / (
            Path(info["file_name"]).stem + "_mask.png"
        )

        if cv2.imwrite(str(output_path), mask):
            saved += 1

    print(f"\n{split.upper()} mask generation complete")
    print("Images:", len(image_map))
    print("Masks saved:", saved)
    print("Missing/unreadable images:", missing)
    print("Output:", output_dir)
