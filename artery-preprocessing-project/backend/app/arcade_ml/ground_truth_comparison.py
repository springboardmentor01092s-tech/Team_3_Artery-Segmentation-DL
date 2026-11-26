from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .coco import STENOSIS_CATEGORY_ID, filter_annotations, index_coco, load_coco, rasterize_polygons


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_exact_training_annotation(image_path: Path, original_filename: str, train_dir: Path) -> tuple[dict, list[dict], Path, str]:
    """Match a source image to train COCO by filename and exact file content."""
    annotation_path = train_dir / "annotations" / "train.json"
    image_dir = train_dir / "images"
    if not image_path.is_file() or not annotation_path.is_file() or not image_dir.is_dir():
        raise FileNotFoundError("ARCADE stenosis/train images or annotations are unavailable.")
    uploaded_hash = sha256_file(image_path)
    coco = load_coco(annotation_path)
    category = next((item for item in coco.get("categories", [])
                     if int(item.get("id", -1)) == STENOSIS_CATEGORY_ID), None)
    if category is None or str(category.get("name", "")).casefold() != "stenosis":
        raise ValueError("COCO category 26 is not explicitly identified as stenosis in the training annotation file.")
    index = index_coco(coco)
    matches = []
    for record in index.values():
        if Path(record["file_name"]).name.casefold() != Path(original_filename).name.casefold():
            continue
        candidate = (image_dir / record["file_name"]).resolve()
        if image_dir.resolve() not in candidate.parents or not candidate.is_file():
            continue
        if sha256_file(candidate) == uploaded_hash:
            matches.append((record, candidate))
    if len(matches) != 1:
        reason = "No exact filename/content match" if not matches else "Multiple exact filename/content matches"
        raise ValueError(f"{reason} in the ARCADE stenosis training split; no annotation was guessed.")
    record, matched_path = matches[0]
    annotations = filter_annotations(record["annotations"], STENOSIS_CATEGORY_ID)
    with Image.open(image_path) as source, Image.open(matched_path) as dataset_image:
        if source.size != dataset_image.size or source.size != (record["width"], record["height"]):
            raise ValueError("Uploaded image, original dataset image, and COCO dimensions do not align.")
    return record, annotations, matched_path, uploaded_hash


def evaluate_masks(ground_truth: np.ndarray, prediction: np.ndarray, candidates: list[dict]) -> tuple[dict, list[dict]]:
    """Pixel overlap metrics and each existing predicted connected component's GT overlap."""
    gt = np.asarray(ground_truth) > 0
    pred = np.asarray(prediction) > 0
    if gt.ndim != 2 or pred.ndim != 2 or gt.shape != pred.shape:
        raise ValueError("Ground-truth and prediction masks must be aligned 2D arrays of equal dimensions.")
    tp = int(np.count_nonzero(gt & pred))
    fp = int(np.count_nonzero(~gt & pred))
    fn = int(np.count_nonzero(gt & ~pred))
    denominator = 2 * tp + fp + fn
    union = tp + fp + fn
    metrics = {
        "tp": tp, "fp": fp, "fn": fn,
        "dice": (2 * tp / denominator) if denominator else 1.0,
        "iou": (tp / union) if union else 1.0,
        "precision": (tp / (tp + fp)) if tp + fp else 0.0,
        "recall": (tp / (tp + fn)) if tp + fn else 0.0,
        "ground_truth_pixels": int(gt.sum()),
        "predicted_pixels": int(pred.sum()),
    }
    count, labels, stats, _ = cv2.connectedComponentsWithStats(pred.astype(np.uint8), connectivity=8)
    components = []
    used_labels = set()
    for candidate in candidates:
        x, y, width, height = (int(candidate[key]) for key in ("x", "y", "width", "height"))
        area = int(candidate.get("pixel_area", -1))
        found = None
        if x >= 0 and y >= 0 and width > 0 and height > 0 and y + height <= pred.shape[0] and x + width <= pred.shape[1]:
            crop = labels[y:y + height, x:x + width]
            label_ids, counts = np.unique(crop[crop > 0], return_counts=True)
            for label_id, pixels in zip(label_ids.tolist(), counts.tolist()):
                label_id = int(label_id)
                stat = stats[label_id]
                if (label_id not in used_labels and pixels == area and
                        (int(stat[cv2.CC_STAT_LEFT]), int(stat[cv2.CC_STAT_TOP]),
                         int(stat[cv2.CC_STAT_WIDTH]), int(stat[cv2.CC_STAT_HEIGHT])) ==
                        (x, y, width, height)):
                    found = label_id
                    break
        if found is None:
            raise ValueError(f"Stored candidate {candidate.get('id')} cannot be aligned with a predicted mask component.")
        used_labels.add(found)
        component = labels == found
        overlap = int(np.count_nonzero(component & gt))
        size = int(component.sum())
        components.append({
            "candidate_id": candidate.get("id"),
            "x": x, "y": y, "width": width, "height": height,
            "predicted_pixels": size,
            "ground_truth_overlap_pixels": overlap,
            "overlap_fraction_of_candidate": overlap / size if size else 0.0,
            "overlaps_ground_truth": overlap > 0,
        })
    if len(used_labels) != count - 1:
        raise ValueError("Predicted mask component count does not match the stored candidate list.")
    return metrics, components


def comparison_visualization(image_rgb: np.ndarray, ground_truth: np.ndarray, prediction: np.ndarray) -> np.ndarray:
    """Create a 2x2 RGB image/mask/classification montage; TP green, FP red, FN blue."""
    image = np.asarray(image_rgb)
    gt = np.asarray(ground_truth) > 0
    pred = np.asarray(prediction) > 0
    if image.ndim != 3 or image.shape[2] != 3 or image.shape[:2] != gt.shape or gt.shape != pred.shape:
        raise ValueError("Image, ground-truth mask, and prediction mask are not aligned.")
    original = cv2.cvtColor(image.astype(np.uint8), cv2.COLOR_RGB2BGR)
    gt_mask = np.repeat((gt.astype(np.uint8) * 255)[..., None], 3, axis=2)
    pred_mask = np.repeat((pred.astype(np.uint8) * 255)[..., None], 3, axis=2)
    combined = np.zeros((*gt.shape, 3), dtype=np.uint8)
    combined[gt & pred] = (40, 210, 40)   # BGR green: TP
    combined[~gt & pred] = (30, 30, 235)  # BGR red: FP
    combined[gt & ~pred] = (235, 100, 30) # BGR blue: FN
    panels = [original, gt_mask, pred_mask, combined]
    titles = ["Original image", "Ground truth (category 26)", "Existing predicted lesion mask", "TP green | FP red | FN blue"]
    titled = []
    for panel, title in zip(panels, titles):
        panel = panel.copy()
        cv2.rectangle(panel, (0, 0), (panel.shape[1], 30), (0, 0, 0), thickness=-1)
        cv2.putText(panel, title, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
        titled.append(panel)
    return np.concatenate((np.concatenate(titled[:2], axis=1), np.concatenate(titled[2:], axis=1)), axis=0)
