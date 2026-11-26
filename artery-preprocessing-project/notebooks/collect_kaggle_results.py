"""Download and compare outputs from the existing ARCADE Kaggle kernel.

This script never uploads data, creates a kernel, reads the test split, or
promotes/replaces an application checkpoint. Run it after the existing kernel
has completed successfully.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KERNEL = "drajuakshayarao/arcade-gpu-model-sweep-2026-11-24"
OUTPUT_NAME = "arcade_model_export.zip"


def kaggle_exe() -> Path:
    exe = ROOT / "backend" / ".venv" / "Scripts" / "kaggle.exe"
    if not exe.is_file():
        raise FileNotFoundError(f"Kaggle CLI executable not found: {exe}")
    return exe


def run_kaggle(*args: str) -> str:
    result = subprocess.run(
        [str(kaggle_exe()), *args], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        env={**os.environ, "KAGGLE_CONFIG_DIR": os.environ.get(
            "KAGGLE_CONFIG_DIR", str(Path.home() / ".kaggle"))},
    )
    if result.returncode:
        raise RuntimeError(result.stdout.strip() or f"Kaggle CLI exited {result.returncode}")
    return result.stdout.strip()


def metric_row(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("dataset_split") != "stenosis/val" or int(data.get("samples_evaluated", 0)) != 200:
        raise ValueError(f"Expected full stenosis validation metrics in {path}")
    if data.get("test_split_used_for_tuning") is not False:
        raise ValueError(f"Test-split integrity flag is missing or unsafe in {path}")
    selected = data["selected_threshold_metrics"]
    global_metrics = selected["global"]
    macro = selected["per_image_macro"]
    candidates = data["candidate_detection"]["by_iou_threshold"]
    small = data["small_target_performance"]["groups"]["small"]
    checkpoint = data.get("checkpoint_metadata", {})
    if "best_stenosis_unet_optimized" in path.name:
        weights = ROOT / "backend" / "checkpoints" / "best_stenosis_unet_optimized.pth"
    else:
        weights = next((p for p in path.parent.rglob("*.pth")), None)
    sha = hashlib.sha256(weights.read_bytes()).hexdigest() if weights else ""
    return {
        "id": path.name.removeprefix("validation_metrics_").removesuffix(".json"),
        "architecture": checkpoint.get("architecture", "unknown"),
        "encoder": checkpoint.get("encoder_name") or "none",
        "input_size": checkpoint.get("image_size"),
        "epoch": checkpoint.get("epoch"),
        "threshold": data.get("selected_threshold"),
        "macro_dice": macro["dice"],
        "macro_iou": macro["iou"],
        "global_precision": global_metrics["precision"],
        "global_recall": global_metrics["recall_sensitivity"],
        "candidate_precision_iou30": candidates["0.30"]["precision"],
        "candidate_recall_iou30": candidates["0.30"]["recall"],
        "candidate_f1_iou30": candidates["0.30"]["f1"],
        "candidate_f1_iou50": candidates["0.50"]["f1"],
        "small_dice": small["macro_dice"],
        "checkpoint": str(weights.relative_to(ROOT)) if weights else "",
        "checkpoint_sha256": sha,
    }


def safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    base = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(base):
                raise ValueError(f"Unsafe path in Kaggle output archive: {item.filename}")
        bundle.extractall(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-download", action="store_true", help="Use an already downloaded output ZIP")
    args = parser.parse_args()
    run_dir = ROOT / "reports" / "kaggle_gpu_run"
    run_dir.mkdir(parents=True, exist_ok=True)
    status = run_kaggle("kernels", "status", KERNEL)
    print(status)
    if "KernelWorkerStatus.COMPLETE" not in status:
        raise RuntimeError("Kernel is not COMPLETE. Preserve its current run and inspect Kaggle status/log first.")
    archive = run_dir / OUTPUT_NAME
    if not args.no_download:
        print(run_kaggle("kernels", "output", KERNEL, "-p", str(run_dir), "-o"))
    if not archive.is_file():
        raise FileNotFoundError(f"Expected Kaggle output archive: {archive}")
    extracted = run_dir / "extracted_v2"
    safe_extract(archive, extracted)

    baseline_path = ROOT / "reports" / "model_validation" / "validation_metrics_best_stenosis_unet_optimized.json"
    rows = [metric_row(baseline_path)]
    for metric_path in extracted.rglob("validation_metrics_*.json"):
        if "best_stenosis_unet_optimized" in metric_path.name:
            continue
        rows.append(metric_row(metric_path))
    baseline = rows[0]
    for row in rows:
        row["delta_macro_dice_vs_baseline"] = row["macro_dice"] - baseline["macro_dice"]
        row["delta_macro_iou_vs_baseline"] = row["macro_iou"] - baseline["macro_iou"]
        row["delta_small_dice_vs_baseline"] = row["small_dice"] - baseline["small_dice"]
        row["delta_candidate_f1_iou30_vs_baseline"] = row["candidate_f1_iou30"] - baseline["candidate_f1_iou30"]
    rows.sort(key=lambda r: r["macro_dice"], reverse=True)
    report = run_dir / "local_validation_comparison.json"
    report.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    csv_path = run_dir / "local_validation_comparison.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Compared {len(rows)-1} downloaded candidate(s) against baseline; reports: {csv_path}, {report}")
    print("No checkpoint is promoted by this script. Review the complete validation metrics, then run local audit/inference and tests before selecting a candidate.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Kaggle result collection stopped: {exc}", file=sys.stderr)
        raise SystemExit(1)
