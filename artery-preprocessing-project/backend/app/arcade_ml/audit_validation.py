"""Read-only ARCADE audit and ground-truth validation for stenosis checkpoint.

Example (from backend): python -m app.arcade_ml.audit_validation
Writes reports/validation_* only inside this project; never modifies ARCADE source data.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw

from app.arcade_ml.coco import STENOSIS_CATEGORY_ID, annotation_bboxes, filter_annotations, index_coco, load_coco, rasterize_polygons
from app.arcade_ml.engine import load_checkpoint, predict_image
from app.arcade_ml.explain import overlay_mask
from app.arcade_ml.localize import extract_candidates, match_localization
from app.arcade_ml.paths import arcade_root, checkpoints_dir, complete_project_root
from app.arcade_ml.postprocess import filter_small_components


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_split(task: str, split: str) -> dict:
    root = arcade_root() / task / split
    image_dir = root / "images"
    annotation_path = root / "annotations" / f"{split}.json"
    if not annotation_path.is_file():
        return {"task": task, "split": split, "error": f"Missing annotations: {annotation_path}"}
    coco = load_coco(annotation_path)
    records = index_coco(coco)
    known_image_ids = {int(item["id"]) for item in coco.get("images", [])}
    image_ids = [int(item["id"]) for item in coco.get("images", [])]
    annotation_ids = [int(item["id"]) for item in coco.get("annotations", []) if "id" in item]
    annotation_orphans = sum(1 for item in coco.get("annotations", []) if int(item.get("image_id", -1)) not in known_image_ids)
    file_to_record = {record["file_name"]: record for record in records.values()}
    actual_files = [p for p in image_dir.iterdir() if p.is_file()] if image_dir.is_dir() else []
    missing = sorted(name for name in file_to_record if not (image_dir / name).is_file())
    orphan = sorted(p.name for p in actual_files if p.name not in file_to_record)
    unreadable, dimension_mismatch, empty, positives = [], [], [], []
    foreground = []
    dimension_counts: Counter[str] = Counter()
    ann_count = 0
    image_hashes = {}
    category_counts: Counter[str] = Counter()
    segmentation_types: Counter[str] = Counter()
    annotations_without_segmentation = 0
    degenerate_polygons = 0
    invalid_bboxes = 0
    for name, record in file_to_record.items():
        path = image_dir / name
        if not path.is_file():
            continue
        try:
            with Image.open(path) as opened:
                opened.verify()
            with Image.open(path) as opened:
                width, height = opened.size
                dimension_counts[f"{width}x{height}"] += 1
                if (width, height) != (record["width"], record["height"]):
                    dimension_mismatch.append({"file": name, "actual": [width, height], "annotation": [record["width"], record["height"]]})
                image_hashes[name] = _hash(path)
                anns = record["annotations"]
                ann_count += len(anns)
                for ann in anns:
                    category_counts[str(ann.get("category_id", "missing"))] += 1
                    segmentation = ann.get("segmentation")
                    segmentation_types["polygon_list" if isinstance(segmentation, list) else type(segmentation).__name__] += 1
                    if not segmentation:
                        annotations_without_segmentation += 1
                    elif isinstance(segmentation, list):
                        polygons = segmentation if segmentation and isinstance(segmentation[0], list) else [segmentation]
                        degenerate_polygons += sum(1 for polygon in polygons if not polygon or len(polygon) < 6 or len(polygon) % 2 != 0)
                    bbox = ann.get("bbox")
                    if bbox is not None and (len(bbox) < 4 or float(bbox[2]) <= 0 or float(bbox[3]) <= 0):
                        invalid_bboxes += 1
                selected = filter_annotations(anns, STENOSIS_CATEGORY_ID) if task == "stenosis" else anns
                mask = rasterize_polygons(width, height, selected)
                count = int(np.count_nonzero(np.asarray(mask)))
                foreground.append(count)
                if count:
                    positives.append(name)
                else:
                    empty.append(name)
        except Exception as exc:
            unreadable.append({"file": name, "error": type(exc).__name__})
    return {
        "task": task, "split": split, "annotation_file": str(annotation_path),
        "coco_image_records": len(records), "physical_image_files": len(actual_files),
        "annotation_records": len(coco.get("annotations", [])), "categories": coco.get("categories", []),
        "annotation_category_counts": dict(category_counts), "segmentation_format_counts": dict(segmentation_types),
        "duplicate_image_ids": len(image_ids) - len(set(image_ids)),
        "duplicate_annotation_ids": len(annotation_ids) - len(set(annotation_ids)),
        "annotations_with_unknown_image_id": annotation_orphans,
        "invalid_bboxes": invalid_bboxes,
        "annotations_without_segmentation": annotations_without_segmentation,
        "degenerate_polygons": degenerate_polygons,
        "missing_images": missing, "orphan_images": orphan, "unreadable_images": unreadable,
        "dimension_mismatches": dimension_mismatch, "dimensions": dict(dimension_counts),
        "empty_target_images": empty, "positive_target_images": len(positives),
        "foreground_pixels": {"min": min(foreground, default=0), "median": float(np.median(foreground)) if foreground else 0,
                               "max": max(foreground, default=0), "total": sum(foreground)},
        "hashes": image_hashes,
    }


def audit_dataset(include_test: bool = False) -> dict:
    # Keep the test split unread during training and validation-based selection.
    split_names = ("train", "val", "test") if include_test else ("train", "val")
    splits = [audit_split(task, split) for task in ("stenosis", "syntax") for split in split_names]
    duplicate_groups, cross_split_duplicates = [], []
    for task in ("stenosis", "syntax"):
        by_hash = {}
        for row in splits:
            if row["task"] != task:
                continue
            for name, digest in row.get("hashes", {}).items():
                by_hash.setdefault(digest, []).append({"split": row["split"], "file": name})
        for entries in by_hash.values():
            if len(entries) > 1:
                group = {"task": task, "matches": entries, "cross_split": len({x["split"] for x in entries}) > 1}
                duplicate_groups.append(group)
                if group["cross_split"]: cross_split_duplicates.append(group)
    stenosis_categories = next((r.get("categories", []) for r in splits if r["task"] == "stenosis" and r["split"] == "train"), [])
    names = [str(item.get("name", "")).lower() for item in stenosis_categories]
    return {
        "dataset_root": str(arcade_root()), "test_split_included": include_test,
        "split_audits": [{k: v for k, v in row.items() if k != "hashes"} for row in splits],
        "exact_duplicate_groups": duplicate_groups,
        "cross_split_exact_duplicates": cross_split_duplicates,
        "stenosis_category_id": STENOSIS_CATEGORY_ID,
        "stenosis_categories_contain_lumen_or_diameter_labels": any("lumen" in n or "diameter" in n for n in names),
        "measurement_conclusion": "COCO stenosis polygons and boxes do not provide calibrated lumen boundaries or reference/minimum lumen diameter measurements.",
    }


def _confusion(pred: np.ndarray, truth: np.ndarray) -> tuple[int, int, int, int]:
    p, t = pred.astype(bool), truth.astype(bool)
    return (int(np.count_nonzero(p & t)), int(np.count_nonzero(p & ~t)),
            int(np.count_nonzero(~p & t)), int(np.count_nonzero(~p & ~t)))


def _metric_from_counts(tp: int, fp: int, fn: int, tn: int) -> dict[str, float]:
    eps = 1e-7
    return {
        "dice": (2 * tp + eps) / (2 * tp + fp + fn + eps),
        "iou": (tp + eps) / (tp + fp + fn + eps),
        "precision": (tp + eps) / (tp + fp + eps),
        "recall": (tp + eps) / (tp + fn + eps),
        "specificity": (tn + eps) / (tn + fp + eps),
    }


def _summarize(rows: list[dict]) -> dict:
    tp = sum(r["tp"] for r in rows); fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows); tn = sum(r["tn"] for r in rows)
    def div(a, b): return float(a / b) if b else 0.0
    precision, recall = div(tp, tp + fp), div(tp, tp + fn)
    return {
        "global": {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                   "dice": div(2 * tp, 2 * tp + fp + fn), "iou": div(tp, tp + fp + fn),
                   "precision": precision, "recall_sensitivity": recall,
                   "f1": div(2 * precision * recall, precision + recall),
                   "specificity": div(tn, tn + fp)},
        "per_image_macro": {key: float(np.mean([r[key] for r in rows])) if rows else 0.0
                            for key in ("dice", "iou", "precision", "recall", "specificity")},
    }


def _draw_comparison(original: np.ndarray, truth: np.ndarray, probability: np.ndarray, threshold: float,
                     candidates: list[dict], destination: Path, label: str, metrics: dict) -> None:
    pred = filter_small_components((probability >= threshold).astype(np.uint8), 20)
    rgb = cv2.cvtColor(original, cv2.COLOR_RGB2BGR)
    gt_overlay = overlay_mask(rgb, truth.astype(np.uint8), color=(0, 180, 50))
    pred_overlay = overlay_mask(rgb, pred.astype(np.uint8), color=(0, 60, 255))
    for box in candidates:
        cv2.rectangle(pred_overlay, (box["x"], box["y"]), (box["x"] + box["width"], box["y"] + box["height"]), (255, 200, 0), 2)
    heat = cv2.applyColorMap((np.clip(probability, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_JET)
    heat = cv2.addWeighted(rgb, 0.5, heat, 0.5, 0)
    panels = [cv2.cvtColor(x, cv2.COLOR_BGR2RGB) for x in (rgb, gt_overlay, pred_overlay, heat)]
    pil_panels = [Image.fromarray(x).resize((512, 512), Image.Resampling.NEAREST) for x in panels]
    canvas = Image.new("RGB", (1024, 1090), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 7), f"{label} | threshold={threshold:.2f} | Dice={metrics['dice']:.3f} | IoU={metrics['iou']:.3f}", fill="black")
    draw.text((10, 22), f"Precision={metrics['precision']:.3f} | Recall={metrics['recall']:.3f} | candidate TP/FP/FN @0.30={metrics['candidate_tp_iou_030']}/{metrics['candidate_fp_iou_030']}/{metrics['candidate_fn_iou_030']}", fill="black")
    captions = ["Original", "Ground-truth category 26", "Prediction and candidate boxes", "Probability heatmap (not Grad-CAM)"]
    for i, (panel, caption) in enumerate(zip(pil_panels, captions)):
        x = (i % 2) * 512; y = 46 + (i // 2) * 519
        canvas.paste(panel, (x, y)); draw.text((x + 8, y + 5), caption, fill="white", stroke_width=2, stroke_fill="black")
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination)


def evaluate_validation(checkpoint: Path, out_dir: Path, device_name: str = "cpu") -> dict:
    device = torch.device(device_name)
    model, metadata = load_checkpoint(checkpoint, device)
    image_size = int(metadata.get("image_size", 256))
    threshold_values = [0.25, 0.35, 0.45, 0.5, 0.55, 0.65, 0.75]
    coco = load_coco(arcade_root() / "stenosis" / "val" / "annotations" / "val.json")
    records = sorted(index_coco(coco).values(), key=lambda rec: rec["file_name"])
    predictions, original_by_name, truth_by_name, boxes_by_name = {}, {}, {}, {}
    model.eval()
    inference_started = time.perf_counter()
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    with torch.inference_mode():
        for rec in records:
            path = arcade_root() / "stenosis" / "val" / "images" / rec["file_name"]
            if not path.is_file():
                continue
            with Image.open(path) as im:
                original = np.asarray(im.convert("RGB"))
            anns = filter_annotations(rec["annotations"], STENOSIS_CATEGORY_ID)
            truth = np.asarray(rasterize_polygons(original.shape[1], original.shape[0], anns)) > 0
            probability = predict_image(model, original, image_size, device,
                                       normalization=metadata.get("normalization", "none"))
            predictions[rec["file_name"]] = probability
            original_by_name[rec["file_name"]] = original
            truth_by_name[rec["file_name"]] = truth
            boxes_by_name[rec["file_name"]] = annotation_bboxes(anns)
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    inference_seconds = time.perf_counter() - inference_started

    threshold_rows, per_threshold = [], {}
    for threshold in threshold_values:
        rows = []
        for name, probability in predictions.items():
            truth = truth_by_name[name]
            pred = filter_small_components((probability >= threshold).astype(np.uint8), 20)
            counts = _confusion(pred, truth)
            tp, fp, fn, tn = counts
            metric = _metric_from_counts(tp, fp, fn, tn)
            rows.append({"file_name": name, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                         "dice": metric["dice"], "iou": metric["iou"], "precision": metric["precision"],
                         "recall": metric["recall"], "specificity": metric["specificity"],
                         "gt_pixels": int(truth.sum()), "pred_pixels": int(pred.sum()), "threshold": threshold})
        summary = _summarize(rows)
        per_threshold[str(threshold)] = {"metrics": summary, "per_image": rows}
        threshold_rows.append({"threshold": threshold, "macro_dice": summary["per_image_macro"]["dice"],
                               "global_dice": summary["global"]["dice"], "macro_iou": summary["per_image_macro"]["iou"]})
    selected = max(threshold_rows, key=lambda row: (row["macro_dice"], row["threshold"]))["threshold"]
    chosen = per_threshold[str(selected)]
    localization_totals = Counter()
    visual_candidates = []
    candidate_threshold_totals = {threshold: Counter() for threshold in (0.3, 0.5)}
    component_areas: list[int] = []
    for name, probability in predictions.items():
        pred = filter_small_components((probability >= selected).astype(np.uint8), 20)
        pred_boxes = extract_candidates(pred, probability, min_area=20)
        for box in pred_boxes:
            component_areas.append(int(box["pixel_area"]))
        per_iou = {}
        for iou_threshold in (0.3, 0.5):
            match = match_localization(pred_boxes, boxes_by_name[name], iou_threshold=iou_threshold)
            per_iou[iou_threshold] = match
            for key in ("tp", "fp", "fn"):
                candidate_threshold_totals[iou_threshold][key] += match[key]
        match = per_iou[0.3]
        for key in ("tp", "fp", "fn"):
            localization_totals[key] += match[key]
        row = next(item for item in chosen["per_image"] if item["file_name"] == name)
        row.update({"candidate_tp_iou_030": per_iou[0.3]["tp"], "candidate_fp_iou_030": per_iou[0.3]["fp"],
                    "candidate_fn_iou_030": per_iou[0.3]["fn"], "candidate_tp_iou_050": per_iou[0.5]["tp"],
                    "candidate_fp_iou_050": per_iou[0.5]["fp"], "candidate_fn_iou_050": per_iou[0.5]["fn"]})
        visual_candidates.append((name, row, pred_boxes))

    # Choose distinct informative validation examples; all selection uses validation labels.
    visual_dir = out_dir / f"validation_comparisons_{checkpoint.stem}"
    selected_visuals = []
    candidates_to_save = []
    if visual_candidates:
        candidates_to_save += [("best_dice", max(visual_candidates, key=lambda x: x[1]["dice"]))]
        candidates_to_save += [("worst_dice", min(visual_candidates, key=lambda x: x[1]["dice"]))]
        candidates_to_save += [("false_positive", max(visual_candidates, key=lambda x: x[1]["fp"]))]
        candidates_to_save += [("false_negative", max(visual_candidates, key=lambda x: x[1]["fn"]))]
        empties = [x for x in visual_candidates if x[1]["gt_pixels"] == 0]
        if empties: candidates_to_save += [("empty_ground_truth", max(empties, key=lambda x: x[1]["pred_pixels"]))]
        positives = [x for x in visual_candidates if x[1]["gt_pixels"] > 0]
        if positives:
            candidates_to_save += [("small_ground_truth", min(positives, key=lambda x: x[1]["gt_pixels"]))]
            candidates_to_save += [("large_ground_truth", max(positives, key=lambda x: x[1]["gt_pixels"]))]
            # Include low, middle, and high target-size examples plus difficult cases.
            ordered_size = sorted(positives, key=lambda x: x[1]["gt_pixels"])
            for label, index in (("small_lesion", 0), ("small_lesion_q25", int((len(ordered_size)-1)*0.25)),
                                 ("median_lesion", int((len(ordered_size)-1)*0.5)),
                                 ("large_lesion_q75", int((len(ordered_size)-1)*0.75))):
                candidates_to_save.append((label, ordered_size[index]))
        for rank, item in enumerate(sorted(visual_candidates, key=lambda x: x[1]["dice"])[:10], start=1):
            candidates_to_save.append((f"low_dice_{rank:02d}", item))
        for rank, item in enumerate(sorted(visual_candidates, key=lambda x: x[1]["fp"], reverse=True)[:10], start=1):
            candidates_to_save.append((f"high_false_positive_{rank:02d}", item))
        for rank, item in enumerate(sorted(visual_candidates, key=lambda x: x[1]["fn"], reverse=True)[:10], start=1):
            candidates_to_save.append((f"high_false_negative_{rank:02d}", item))
        # Fill to at least 50 distinct representative images using Dice ranks.
        already = {item[1][0] for item in candidates_to_save}
        ranked = sorted(visual_candidates, key=lambda x: x[1]["dice"])
        for rank in np.linspace(0, len(ranked) - 1, num=len(ranked), dtype=int):
            item = ranked[int(rank)]
            if item[0] not in already:
                candidates_to_save.append((f"representative_{len(already)+1:02d}", item))
                already.add(item[0])
            if len(already) >= 50:
                break
    seen = set()
    for label, (name, row, pred_boxes) in candidates_to_save:
        if name in seen: continue
        seen.add(name)
        _draw_comparison(original_by_name[name], truth_by_name[name], predictions[name], selected,
                         pred_boxes, visual_dir / f"{label}_{Path(name).stem}.png", label, row)
        selected_visuals.append({"label": label, "file_name": name,
                                 "image_path": f"{label}_{Path(name).stem}.png", "metrics": row})

    candidate_tp, candidate_fp, candidate_fn = (localization_totals[k] for k in ("tp", "fp", "fn"))
    candidate_precision = candidate_tp / (candidate_tp + candidate_fp) if candidate_tp + candidate_fp else 0.0
    candidate_recall = candidate_tp / (candidate_tp + candidate_fn) if candidate_tp + candidate_fn else 0.0
    candidate_by_iou = {}
    for iou_threshold, counts in candidate_threshold_totals.items():
        tp_i, fp_i, fn_i = (counts[k] for k in ("tp", "fp", "fn"))
        precision_i = tp_i / (tp_i + fp_i) if tp_i + fp_i else 0.0
        recall_i = tp_i / (tp_i + fn_i) if tp_i + fn_i else 0.0
        candidate_by_iou[f"{iou_threshold:.2f}"] = {"tp": tp_i, "fp": fp_i, "fn": fn_i,
            "precision": precision_i, "recall": recall_i,
            "f1": 2 * precision_i * recall_i / (precision_i + recall_i) if precision_i + recall_i else 0.0,
            "matching": "one-to-one greedy matching, predictions ordered by mean predicted probability"}
    positive_rows = [row for row in chosen["per_image"] if row["gt_pixels"] > 0]
    target_areas = [row["gt_pixels"] for row in positive_rows]
    q25, q75 = (float(np.quantile(target_areas, q)) for q in (0.25, 0.75)) if target_areas else (0.0, 0.0)
    target_size_groups = {
        "small": [row for row in positive_rows if row["gt_pixels"] <= q25],
        "medium": [row for row in positive_rows if q25 < row["gt_pixels"] < q75],
        "large": [row for row in positive_rows if row["gt_pixels"] >= q75],
    }
    target_size_metrics = {"definition": "positive validation images grouped by category-26 target area: small <= Q25, medium between Q25 and Q75, large >= Q75",
        "q25_pixels": q25, "q75_pixels": q75, "groups": {}}
    for size_name, size_rows in target_size_groups.items():
        target_size_metrics["groups"][size_name] = {"image_count": len(size_rows),
            "macro_dice": float(np.mean([row["dice"] for row in size_rows])) if size_rows else 0.0,
            "macro_iou": float(np.mean([row["iou"] for row in size_rows])) if size_rows else 0.0,
            "macro_precision": float(np.mean([row["precision"] for row in size_rows])) if size_rows else 0.0,
            "macro_recall": float(np.mean([row["recall"] for row in size_rows])) if size_rows else 0.0,
            "candidate_counts_iou_030": {key: sum(row[f"candidate_{key}_iou_030"] for row in size_rows) for key in ("tp", "fp", "fn")}}
    small_target_performance = target_size_metrics

    postprocess_comparison = []
    selected_rows_by_name = {row["file_name"]: row for row in chosen["per_image"]}
    for min_area in (0, 20, 50, 100):
        pp_rows=[]; pp_candidate={iou:Counter() for iou in (0.3,0.5)}
        pp_candidate_by_size={iou:{name:Counter() for name in target_size_groups} for iou in (0.3,0.5)}
        for name, probability in predictions.items():
            raw=(probability >= selected).astype(np.uint8)
            pred=filter_small_components(raw,min_area) if min_area else raw
            tp,fp,fn,tn=_confusion(pred,truth_by_name[name]); pixel=_metric_from_counts(tp,fp,fn,tn)
            pp_rows.append({"file_name":name,**pixel,"tp":tp,"fp":fp,"fn":fn,"tn":tn})
            boxes=extract_candidates(pred,probability,min_area=max(1,min_area))
            target_row=selected_rows_by_name[name]
            if target_row["gt_pixels"] <= q25:
                size_name="small"
            elif target_row["gt_pixels"] >= q75:
                size_name="large"
            else:
                size_name="medium"
            for iou in (0.3,0.5):
                matched=match_localization(boxes,boxes_by_name[name],iou_threshold=iou)
                for key in ("tp","fp","fn"): pp_candidate[iou][key]+=matched[key]
                if target_row["gt_pixels"] > 0:
                    for key in ("tp","fp","fn"):
                        pp_candidate_by_size[iou][size_name][key]+=matched[key]
        pp_summary=_summarize(pp_rows)
        pp_size_metrics={}
        for size_name,size_records in target_size_groups.items():
            names={record["file_name"] for record in size_records}
            subset=[record for record in pp_rows if record["file_name"] in names]
            subset_summary=_summarize(subset)
            pp_size_metrics[size_name]={"macro_dice":subset_summary["per_image_macro"]["dice"],
                "macro_iou":subset_summary["per_image_macro"]["iou"],
                "candidate_counts_iou_030":dict(pp_candidate_by_size[0.3][size_name])}
        postprocess_comparison.append({"minimum_component_area_pixels":min_area,
            "macro_dice":pp_summary["per_image_macro"]["dice"],"macro_iou":pp_summary["per_image_macro"]["iou"],
            "global_dice":pp_summary["global"]["dice"],"global_precision":pp_summary["global"]["precision"],
            "global_recall":pp_summary["global"]["recall_sensitivity"],
            "candidate_counts":{f"iou_{iou:.2f}":dict(counts) for iou,counts in pp_candidate.items()},
            "target_size_metrics":pp_size_metrics})
    result = {
        "checkpoint": str(checkpoint), "checkpoint_metadata": {"architecture": metadata.get("resolved_architecture"),
            "encoder_name": metadata.get("encoder_name"), "normalization": metadata.get("normalization", "none"),
            "image_size": image_size, "epoch": metadata.get("epoch"), "stored_val_dice": metadata.get("val_dice", metadata.get("best_val_dice")),
            "stored_val_iou": metadata.get("val_iou")},
        "device": str(device), "dataset_split": "stenosis/val", "samples_evaluated": len(predictions),
        "target": "category_id=26 polygon rasterization", "prediction_threshold_selected_by": "highest per-image macro Dice on validation only",
        "minimum_component_area_pixels": 20, "candidate_iou_match_threshold": 0.3,
        "threshold_comparison": threshold_rows, "selected_threshold": selected,
        "selected_threshold_metrics": chosen["metrics"], "candidate_detection": {
            "tp": candidate_tp, "fp": candidate_fp, "fn": candidate_fn,
            "precision": candidate_precision, "recall": candidate_recall,
            "by_iou_threshold": candidate_by_iou,
            "component_pixel_area_distribution": {"count": len(component_areas), "min": min(component_areas, default=0),
                "median": float(np.median(component_areas)) if component_areas else 0.0, "max": max(component_areas, default=0)},
            "meaning": "IoU-matched connected components against category-26 annotated boxes; not clinical confidence."},
        "small_target_performance": small_target_performance,
        "per_image": chosen["per_image"], "visual_examples": selected_visuals,
        "test_split_used_for_tuning": False,
        "inference_performance": {"wall_seconds_for_all_samples_including_image_io_preprocess_and_predict": inference_seconds,
            "seconds_per_image": inference_seconds / len(predictions) if predictions else None,
            "checkpoint_size_bytes": checkpoint.stat().st_size,
            "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
            "device": str(device),
            "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else None},
        "postprocess_comparison_at_selected_threshold": postprocess_comparison,
        "clinical_measurements": {"percentage_narrowing": None, "severity": None,
            "reason": "The ARCADE annotations provide lesion polygons/boxes, not calibrated vessel lumen boundaries or reference/minimum diameters."},
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = out_dir / f"validation_metrics_{checkpoint.stem}.json"
    per_image_path = out_dir / f"validation_per_image_{checkpoint.stem}.csv"
    (metrics_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    threshold_path = checkpoint.with_suffix(checkpoint.suffix + ".threshold.json")
    threshold_path.write_text(json.dumps({"threshold": selected,
        "selection_method": "validation_macro_dice", "validation_report": metrics_path.name,
        "validation_macro_dice": chosen["metrics"]["per_image_macro"]["dice"]}, indent=2), encoding="utf-8")
    with per_image_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(chosen["per_image"][0]) if chosen["per_image"] else ["file_name"])
        writer.writeheader(); writer.writerows(chosen["per_image"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, default=checkpoints_dir() / "best_stenosis_unet_optimized.pth")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--include-test-integrity-audit", action="store_true",
                        help="Read test data for integrity only; unnecessary for validation-based experimentation.")
    args = parser.parse_args()
    report_root = complete_project_root() / "reports" / "model_validation"
    audit = audit_dataset(include_test=args.include_test_integrity_audit)
    report_root.mkdir(parents=True, exist_ok=True)
    audit_path = report_root / ("dataset_audit.json" if args.include_test_integrity_audit else "dataset_audit_train_val.json")
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    if not args.audit_only:
        result = evaluate_validation(args.checkpoint, report_root, args.device)
        print(json.dumps({"samples": result["samples_evaluated"], "threshold": result["selected_threshold"],
                          "metrics": result["selected_threshold_metrics"], "candidate_detection": result["candidate_detection"]}, indent=2))
    print(f"Audit report: {audit_path}")


if __name__ == "__main__":
    main()
