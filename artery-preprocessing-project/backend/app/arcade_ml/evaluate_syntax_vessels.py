"""Evaluate a separately trained SYNTAX vessel-region model on syntax/val only.

The target is the union of ARCADE's SYNTAX coronary-segment polygons. These
annotations are not stenosis lesion masks and are not validated diameter or
reference-segment measurements. The test split is never opened here.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from app.arcade_ml.coco import index_coco, load_coco, rasterize_polygons
from app.arcade_ml.engine import load_checkpoint, predict_image
from app.arcade_ml.paths import arcade_root, checkpoints_dir, complete_project_root


def _metrics(tp: int, fp: int, fn: int, tn: int) -> dict[str, float]:
    eps = 1e-7
    return {
        "dice": (2 * tp + eps) / (2 * tp + fp + fn + eps),
        "iou": (tp + eps) / (tp + fp + fn + eps),
        "precision": (tp + eps) / (tp + fp + eps),
        "recall": (tp + eps) / (tp + fn + eps),
        "specificity": (tn + eps) / (tn + fp + eps),
    }


def _score(prediction: np.ndarray, target: np.ndarray) -> dict:
    pred, truth = prediction.astype(bool), target.astype(bool)
    tp = int(np.count_nonzero(pred & truth))
    fp = int(np.count_nonzero(pred & ~truth))
    fn = int(np.count_nonzero(~pred & truth))
    tn = int(np.count_nonzero(~pred & ~truth))
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, **_metrics(tp, fp, fn, tn)}


def _overlay(rgb: np.ndarray, mask: np.ndarray, color: tuple[int, int, int]) -> np.ndarray:
    result = rgb.copy().astype(np.float32)
    selected = mask.astype(bool)
    result[selected] = result[selected] * 0.5 + np.asarray(color, dtype=np.float32) * 0.5
    return np.clip(result, 0, 255).astype(np.uint8)


def evaluate_syntax_vessel_checkpoint(
    checkpoint: Path,
    out_dir: Path,
    device_name: str = "cpu",
    thresholds: tuple[float, ...] = (0.25, 0.35, 0.45, 0.5, 0.55, 0.65, 0.75),
) -> dict:
    device = torch.device(device_name)
    model, metadata = load_checkpoint(checkpoint, device)
    if metadata.get("task") != "syntax":
        raise ValueError("Expected an experimental checkpoint trained for task='syntax'.")

    validation_root = arcade_root() / "syntax" / "val"
    coco = load_coco(validation_root / "annotations" / "val.json")
    records = sorted(index_coco(coco).values(), key=lambda record: record["file_name"])
    examples: list[tuple[str, np.ndarray, np.ndarray]] = []
    model.eval()
    with torch.inference_mode():
        for record in records:
            image_path = validation_root / "images" / record["file_name"]
            if not image_path.is_file():
                continue
            with Image.open(image_path) as image:
                original = np.asarray(image.convert("RGB"))
            target = np.asarray(
                rasterize_polygons(original.shape[1], original.shape[0], record["annotations"])
            ) > 0
            probability = predict_image(
                model,
                original,
                int(metadata.get("image_size", 256)),
                device,
                normalization=metadata.get("normalization", "none"),
            )
            if probability.shape != target.shape:
                raise ValueError(f"Prediction/target shape mismatch for {record['file_name']}.")
            examples.append((record["file_name"], probability, target))

    if not examples:
        raise ValueError("No syntax validation images were available for evaluation.")

    comparisons = []
    scored: dict[float, list[dict]] = {}
    for threshold in thresholds:
        rows = []
        for file_name, probability, target in examples:
            row = {"file_name": file_name, **_score(probability >= threshold, target)}
            row["ground_truth_pixels"] = int(target.sum())
            row["predicted_pixels"] = int((probability >= threshold).sum())
            rows.append(row)
        scored[threshold] = rows
        comparisons.append({
            "threshold": threshold,
            "validation_macro_dice": float(np.mean([row["dice"] for row in rows])),
            "validation_macro_iou": float(np.mean([row["iou"] for row in rows])),
        })

    selected_threshold = max(
        comparisons, key=lambda item: (item["validation_macro_dice"], item["threshold"])
    )["threshold"]
    rows = scored[selected_threshold]
    totals = {key: sum(row[key] for row in rows) for key in ("tp", "fp", "fn", "tn")}
    global_metrics = _metrics(**totals)
    visual_dir = out_dir / f"{checkpoint.stem}_syntax_validation_examples"
    visual_examples = []
    ranked = sorted(rows, key=lambda row: row["dice"])
    selections = []
    if ranked:
        selections.extend([("worst_dice", ranked[0]), ("best_dice", ranked[-1])])
        selections.append(("median_dice", ranked[len(ranked) // 2]))
    seen_images = set()
    for label, row in selections:
        file_name = row["file_name"]
        if file_name in seen_images:
            continue
        seen_images.add(file_name)
        example = next(item for item in examples if item[0] == file_name)
        with Image.open(validation_root / "images" / file_name) as image:
            original = np.asarray(image.convert("RGB"))
        _, probability, target = example
        prediction = probability >= selected_threshold
        panels = [original, _overlay(original, target, (0, 200, 60)), _overlay(original, prediction, (255, 40, 40))]
        comparison = Image.fromarray(np.concatenate(panels, axis=1))
        visual_dir.mkdir(parents=True, exist_ok=True)
        visual_name = f"{label}_{Path(file_name).stem}.png"
        comparison.save(visual_dir / visual_name)
        visual_examples.append({"label": label, "file_name": file_name, "image_path": str(visual_dir / visual_name),
                                "validation_metrics": row})

    report = {
        "task": "syntax",
        "dataset_split": "syntax/val",
        "samples_evaluated": len(rows),
        "target_semantics": "union of annotated SYNTAX coronary artery segment polygons; annotated segments only",
        "not_a_lumen_caliber_measurement": True,
        "test_split_used": False,
        "checkpoint": str(checkpoint),
        "architecture": metadata.get("resolved_architecture"),
        "image_size": metadata.get("image_size"),
        "threshold_selection": "validation macro Dice; evaluated validation split only",
        "threshold_comparison": comparisons,
        "selected_threshold": selected_threshold,
        "selected_validation_macro_dice": comparisons[
            next(i for i, item in enumerate(comparisons) if item["threshold"] == selected_threshold)
        ]["validation_macro_dice"],
        "selected_validation_macro_iou": comparisons[
            next(i for i, item in enumerate(comparisons) if item["threshold"] == selected_threshold)
        ]["validation_macro_iou"],
        "global_pixel_metrics": {**totals, **global_metrics},
        "per_image": rows,
        "visual_examples": visual_examples,
        "limitations": [
            "This is an experimental coronary artery segment-region model, not a clinically validated lumen-caliber estimator.",
            "ARCADE SYNTAX annotations cover labeled SYNTAX segments and may omit branches; background is not proof of absence of vessel.",
            "The PNG images contain no physical spacing metadata, and the annotations do not identify stenosis reference segments.",
            "This report does not calculate diameter or percentage narrowing.",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{checkpoint.stem}_syntax_validation.json"
    csv_path = out_dir / f"{checkpoint.stem}_syntax_validation_per_image.csv"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report["report_json"] = str(json_path)
    report["report_csv"] = str(csv_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    report_dir = complete_project_root() / "reports" / "vessel_segmentation"
    report = evaluate_syntax_vessel_checkpoint(args.checkpoint, report_dir, args.device)
    print(json.dumps({key: report[key] for key in (
        "dataset_split", "samples_evaluated", "architecture", "selected_threshold",
        "selected_validation_macro_dice", "selected_validation_macro_iou", "global_pixel_metrics",
        "report_json", "report_csv",
    )}, indent=2))


if __name__ == "__main__":
    main()
