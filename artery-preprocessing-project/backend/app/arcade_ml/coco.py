from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

STENOSIS_CATEGORY_ID = 26


def load_coco(json_path: Path) -> dict[str, Any]:
    with json_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def index_coco(coco: dict[str, Any]) -> dict[int, dict[str, Any]]:
    anns_by_image: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for ann in coco.get("annotations", []):
        anns_by_image[int(ann["image_id"])].append(ann)
    images = {}
    for image in coco.get("images", []):
        image_id = int(image["id"])
        images[image_id] = {
            "id": image_id,
            "file_name": image["file_name"],
            "width": int(image.get("width", 0)),
            "height": int(image.get("height", 0)),
            "annotations": anns_by_image.get(image_id, []),
        }
    return images


def filter_annotations(
    annotations: list[dict[str, Any]],
    category_id: int | None = None,
) -> list[dict[str, Any]]:
    if category_id is None:
        return list(annotations)
    return [ann for ann in annotations if int(ann.get("category_id", -1)) == category_id]


def rasterize_polygons(
    width: int,
    height: int,
    annotations: list[dict[str, Any]],
    fill: int = 255,
) -> Image.Image:
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for ann in annotations:
        segmentation = ann.get("segmentation") or []
        if not isinstance(segmentation, list):
            continue
        polygons = segmentation if segmentation and isinstance(segmentation[0], list) else [segmentation]
        for polygon in polygons:
            if not polygon or len(polygon) < 6:
                continue
            points = [(float(polygon[i]), float(polygon[i + 1])) for i in range(0, len(polygon) - 1, 2)]
            if len(points) >= 3:
                draw.polygon(points, fill=fill)
    return mask


def annotation_bboxes(annotations: list[dict[str, Any]]) -> list[dict[str, float]]:
    boxes = []
    for ann in annotations:
        bbox = ann.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        x, y, w, h = [float(v) for v in bbox[:4]]
        boxes.append(
            {
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "area": float(ann.get("area", w * h)),
                "category_id": int(ann.get("category_id", 0)),
                "annotation_id": int(ann.get("id", 0)),
            }
        )
    return boxes
