import csv
import hashlib
import io
import json
import logging
import threading
import textwrap
import uuid
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.arcade_ml.engine import summarize_checkpoint
from app.arcade_ml.engine import get_device, load_checkpoint, predict_image
from app.arcade_ml.inference import DIAMETER_MEASUREMENT_UNAVAILABLE, StenosisAnalyzer
from app.arcade_ml.ground_truth_comparison import (
    comparison_visualization,
    evaluate_masks,
    find_exact_training_annotation,
)
from app.arcade_ml.coco import rasterize_polygons
from app.arcade_ml.postprocess import filter_small_components
from app.arcade_ml.vessel_width import draw_width_visualizations, measure_vessel_region_widths
from app.arcade_ml.explain import attribution_heatmap, encode_png, integrated_gradients_attribution
from app.arcade_ml.paths import checkpoints_dir, reports_dir, stenosis_split_dir
from app.core.config import get_settings
from app.core.deps import get_current_user, get_db, require_permission
from app.core.permissions import Permission
from app.models.analysis import StenosisAnalysis
from app.models.case import Case
from app.models.image import UploadedImage
from app.models.preprocessing import PreprocessingRun
from app.models.user import User
from app.repositories import cases as case_repo
from app.services import case_service, image_service
from app.preprocessing.pipeline import load_image
from app.utils.audit import record_audit
from app.utils.files import resolve_inside

router = APIRouter(tags=["segmentation and reports"])
logger = logging.getLogger(__name__)
_model_lock = threading.Lock()


def _analysis_dir() -> Path:
    path = get_settings().resolved_analysis_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _model_path() -> Path:
    return get_settings().resolved_checkpoint_path()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=2)
def _load_analyzer_cached(checkpoint: str, checkpoint_sha256: str) -> StenosisAnalyzer:
    # Include content identity in the cache key so a replacement file is never
    # mistaken for the weights already loaded from the same path.
    path = Path(checkpoint)
    if _sha256_file(path) != checkpoint_sha256:
        raise RuntimeError("Checkpoint changed while loading model weights.")
    analyzer = StenosisAnalyzer(path)
    if _sha256_file(path) != checkpoint_sha256:
        raise RuntimeError("Checkpoint changed while loading model weights.")
    return analyzer


def _load_analyzer(checkpoint: str) -> StenosisAnalyzer:
    path = Path(checkpoint)
    return _load_analyzer_cached(str(path), _sha256_file(path))


def _experimental_vessel_checkpoint() -> Path:
    return checkpoints_dir() / "syntax_unet8_experiment.pth"


@lru_cache(maxsize=1)
def _load_vessel_region_model(checkpoint: str):
    model, metadata = load_checkpoint(Path(checkpoint), get_device())
    if metadata.get("task") != "syntax":
        raise ValueError("Experimental vessel-region checkpoint must be trained with task='syntax'.")
    return model, metadata


def _experimental_vessel_threshold(checkpoint: Path) -> float:
    report = reports_dir() / "vessel_segmentation" / f"{checkpoint.stem}_syntax_validation.json"
    if not report.is_file():
        raise ValueError("The experimental vessel model needs its validation-selected threshold report.")
    data = json.loads(report.read_text(encoding="utf-8"))
    if data.get("dataset_split") != "syntax/val" or data.get("test_split_used") is not False:
        raise ValueError("The experimental vessel threshold report is not a valid validation-only report.")
    threshold = float(data["selected_threshold"])
    if not 0.0 < threshold < 1.0:
        raise ValueError("The experimental vessel validation threshold is invalid.")
    return threshold


def _analyze_vessel_region(image_bgr: np.ndarray, checkpoint: Path) -> dict:
    model, metadata = _load_vessel_region_model(str(checkpoint.resolve()))
    threshold = _experimental_vessel_threshold(checkpoint)
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    probability = predict_image(model, rgb, int(metadata.get("image_size", 256)), get_device(),
                                normalization=metadata.get("normalization", "none"))
    mask = filter_small_components(probability >= threshold, min_area=30)
    widths = measure_vessel_region_widths(mask)
    overlay, cross_sections = draw_width_visualizations(image_bgr, mask, widths)
    ok_mask, mask_png = cv2.imencode(".png", (mask.astype(np.uint8) * 255))
    if not ok_mask:
        raise RuntimeError("Unable to encode the vessel-region mask.")
    return {
        "analysis_mode": "vessel_region_experimental",
        "target_semantics": "union of annotated SYNTAX coronary artery segments; not a validated lumen boundary",
        "probability": probability,
        "binary_mask": mask,
        "n_candidates": 0,
        "region_component_count": widths["component_count"],
        "foreground_pixels": int(mask.sum()),
        "threshold": threshold,
        "min_area": 30,
        "candidates": [],
        "width_measurements": widths["measurements"],
        "minimum_estimated_vessel_region_width_px": widths["minimum_width_px"],
        "width_unit": "pixel",
        "width_semantics": widths["semantics"],
        "width_quality_notes": widths["quality_notes"],
        "percentage_narrowing": None,
        "severity": None,
        "diameter_measurement": {
            **DIAMETER_MEASUREMENT_UNAVAILABLE,
            "reason": "Unable to calculate: these are SYNTAX vessel-region widths in pixels, not validated lumen diameters; calibration and a reference lumen segment are unavailable.",
        },
        "limitations": [
            "Experimental SYNTAX segment-region prediction; not validated lumen segmentation.",
            "Widths are estimated pixels along local perpendicular cross-sections, not lumen diameters.",
            "No physical calibration or validated reference segment is available; stenosis percentage is unavailable.",
        ],
        "model": {"architecture": metadata.get("resolved_architecture"), "image_size": metadata.get("image_size"),
                  "checkpoint": checkpoint.name, "experimental": True, "task": "syntax",
                  "validation_threshold": threshold},
        "images": {
            "mask_png": encode_png((mask.astype(np.uint8) * 255)),
            "overlay_png": encode_png(overlay),
            "centerline_png": encode_png(overlay),
            "cross_sections_png": encode_png(cross_sections),
            "heatmap_png": encode_png(cv2.applyColorMap(np.clip(probability * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_TURBO)),
        },
    }


def _active_validation_report() -> tuple[Path, dict] | None:
    checkpoint = _model_path()
    root = reports_dir() / "model_validation"
    report_path = root / f"validation_metrics_{checkpoint.stem}.json"
    if not report_path.is_file() and checkpoint.name == "best_stenosis_unet_optimized.pth":
        report_path = root / "validation_metrics.json"
    if not report_path.is_file():
        return None
    return report_path, json.loads(report_path.read_text(encoding="utf-8"))


def _output(row: StenosisAnalysis) -> dict:
    data = json.loads(row.result_json)
    data.setdefault("diameter_measurement", dict(DIAMETER_MEASUREMENT_UNAVAILABLE))
    data.setdefault("percentage_narrowing", None)
    data.setdefault("severity", None)
    data.update({"id": row.id, "case_id": row.case_id, "image_id": row.image_id,
                 "created_at": row.created_at.isoformat() if row.created_at else None,
                 "model_name": row.model_name, "status": row.status})
    data["artifacts"] = {key: f"/api/analyses/{row.id}/artifacts/{key}" for key in json.loads(row.artifacts_json)}
    return data


def _image_calibration_summary(loaded) -> dict:
    metadata = loaded.metadata or {}
    spacing = metadata.get("pixel_spacing")
    status = metadata.get("pixel_spacing_status", "unavailable")
    valid_reported_spacing = (
        loaded.is_dicom
        and status == "reported_valid_values"
        and isinstance(spacing, list)
        and len(spacing) == 2
    )
    if valid_reported_spacing:
        reason = (
            "Positive DICOM PixelSpacing values are reported in row/column order. "
            "They are provenance only: angiographic calibration, magnification, and transform suitability "
            "have not been verified, so these values are not used for lumen measurements."
        )
        row_spacing, column_spacing = spacing
    else:
        row_spacing = column_spacing = None
        if loaded.is_dicom and status == "invalid_values":
            reason = "DICOM PixelSpacing is missing a valid pair of finite positive values and was not retained."
        elif loaded.is_dicom:
            reason = "The DICOM image does not report PixelSpacing."
        else:
            reason = "Raster image has no DICOM PixelSpacing metadata."
    return {
        "is_dicom": bool(loaded.is_dicom),
        "status": status if loaded.is_dicom else "unavailable",
        "pixel_spacing_status": status if loaded.is_dicom else "unavailable",
        "source": "DICOM PixelSpacing" if valid_reported_spacing else None,
        "pixel_spacing_row_column_mm": [row_spacing, column_spacing] if valid_reported_spacing else None,
        "row_spacing_mm_per_pixel": row_spacing,
        "column_spacing_mm_per_pixel": column_spacing,
        "calibration_type": metadata.get("pixel_spacing_calibration_type") if loaded.is_dicom else None,
        "calibration_verified": False,
        "transform_verified": False,
        "used_for_measurement": False,
        "reason": reason,
    }


@router.get("/api/models/info")
def model_info(user: User = Depends(get_current_user)):
    path = _model_path()
    if not path.is_file():
        return {"available": False, "checkpoint": path.name, "message": "Configured model checkpoint is missing."}
    try:
        with _model_lock:
            info = _load_analyzer(str(path.resolve())).info()
        info.pop("checkpoint", None)
        return {"available": True, "active_checkpoint": path.name, **info}
    except Exception as exc:
        logger.exception("Unable to load segmentation model")
        return {"available": False, "checkpoint": path.name, "message": f"Checkpoint could not be loaded: {type(exc).__name__}."}


@router.get("/api/models/compare")
def compare_models(user: User = Depends(get_current_user)):
    directory = checkpoints_dir()
    models = []
    for path in sorted(directory.glob("*.pth")):
        try:
            item = summarize_checkpoint(path)
            item.pop("checkpoint", None)
            validation_path = reports_dir() / "model_validation" / f"validation_metrics_{path.stem}.json"
            if not validation_path.is_file() and path.name == "best_stenosis_unet_optimized.pth":
                validation_path = reports_dir() / "model_validation" / "validation_metrics.json"
            if validation_path.is_file():
                report = json.loads(validation_path.read_text(encoding="utf-8"))
                item["validation_evaluation"] = {
                    "split": report["dataset_split"], "samples": report["samples_evaluated"],
                    "threshold": report["selected_threshold"], "metrics": report["selected_threshold_metrics"],
                    "candidate_detection": report["candidate_detection"],
                    "selection_method": report["prediction_threshold_selected_by"],
                }
            models.append(item)
        except Exception as exc:
            logger.warning("Skipping unreadable model checkpoint %s (%s)", path.name, type(exc).__name__)
            models.append({"name": path.name, "kind": "checkpoint", "available": False,
                           "note": f"Checkpoint metadata could not be read ({type(exc).__name__})."})
    return {"models": models, "comparison_note": "Validation evaluations use the same 200 category-26 images, original 512x512 coordinates, 20-pixel component filter, and validation-selected threshold protocol. Checkpoint metadata is shown separately where evaluations are absent."}


@router.get("/api/models/validation/examples")
def validation_examples(user: User = Depends(get_current_user)):
    result = _active_validation_report()
    if result is None:
        return []
    _report_path, report = result
    return [{"label": item["label"], "file_name": item["file_name"], "metrics": item["metrics"],
             "image_url": f"/api/models/validation/examples/{Path(item['image_path']).name}"}
            for item in report.get("visual_examples", []) if item.get("image_path")]


@router.get("/api/models/validation/examples/{file_name}")
def validation_example_image(file_name: str, user: User = Depends(get_current_user)):
    result = _active_validation_report()
    if result is None:
        raise HTTPException(status_code=404, detail="No active checkpoint validation report is available.")
    report_path, report = result
    allowed = {Path(item.get("image_path", "")).name for item in report.get("visual_examples", [])}
    if file_name not in allowed:
        raise HTTPException(status_code=404, detail="Validation example not found.")
    directory = report_path.parent / f"validation_comparisons_{_model_path().stem}"
    if not directory.is_dir():
        directory = report_path.parent / "validation_comparisons"
    path = resolve_inside(directory, file_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Validation image file is missing.")
    return FileResponse(path, media_type="image/png", filename=file_name)


@router.post("/api/cases/{case_id}/analyze", status_code=status.HTTP_201_CREATED)
def analyze_case(case_id: str, mode: str = Query(default="lesion", pattern="^(lesion|vessel_region_experimental)$"),
                 db: Session = Depends(get_db),
                 user: User = Depends(require_permission(Permission.IMAGE_PREPROCESS))):
    case = case_service.get_accessible_case(db, user, case_id)
    if not case.images:
        raise HTTPException(status_code=400, detail="Upload an image before running segmentation.")
    image = max(case.images, key=lambda item: item.uploaded_at)
    source = image_service.original_path(image)
    if not source.is_file():
        raise HTTPException(status_code=404, detail="Stored image file is missing.")
    checkpoint = _model_path() if mode == "lesion" else _experimental_vessel_checkpoint()
    if not checkpoint.is_file():
        detail = ("Segmentation checkpoint is unavailable. Configure MODEL_CHECKPOINT." if mode == "lesion"
                  else "Experimental SYNTAX vessel-region checkpoint is unavailable.")
        raise HTTPException(status_code=503, detail=detail)
    loaded = load_image(source)
    arr = loaded.array
    if arr.ndim == 2:
        arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    elif arr.ndim == 3 and arr.shape[2] == 4:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    elif arr.ndim == 3 and arr.shape[2] == 3:
        arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    else:
        raise HTTPException(status_code=422, detail="Image color layout is not supported for segmentation.")
    if arr.dtype != np.uint8:
        finite = np.nan_to_num(arr.astype(np.float32), copy=False)
        lo, hi = float(finite.min()), float(finite.max())
        arr = np.zeros(finite.shape, dtype=np.uint8) if hi <= lo else np.clip((finite - lo) * (255 / (hi - lo)), 0, 255).astype(np.uint8)
    try:
        with _model_lock:
            checkpoint_hash = _sha256_file(checkpoint)
            if mode == "lesion":
                analyzer = _load_analyzer(str(checkpoint.resolve()))
                result = analyzer.analyze(arr)
            else:
                result = _analyze_vessel_region(arr, checkpoint)
            if mode == "lesion" and _sha256_file(checkpoint) != checkpoint_hash:
                raise RuntimeError("Checkpoint changed during analysis.")
    except Exception as exc:
        logger.exception("Segmentation inference failed.")
        raise HTTPException(status_code=503, detail=f"Segmentation could not be completed ({type(exc).__name__}).") from exc

    analysis_id = str(uuid.uuid4())
    folder = _analysis_dir()
    artifact_names = {}
    for key, content in result["images"].items():
        artifact_key = key.removesuffix("_png")
        filename = f"{analysis_id}_{artifact_key}.png"
        resolve_inside(folder, filename).write_bytes(content)
        artifact_names[artifact_key] = filename
    model = dict(result["model"])
    model.pop("checkpoint", None)
    measurement = result.get("diameter_measurement", dict(DIAMETER_MEASUREMENT_UNAVAILABLE))
    image_calibration = _image_calibration_summary(loaded)
    saved = {"analysis_mode": mode, "target_semantics": result.get("target_semantics", "category-26 stenosis lesion regions"),
             "candidate_count": result["n_candidates"], "foreground_pixels": result["foreground_pixels"],
             "threshold": result["threshold"], "min_area": result["min_area"], "candidates": result["candidates"],
             "percentage_narrowing": measurement.get("stenosis_percentage"), "severity": None,
             "diameter_measurement": measurement, "image_calibration": image_calibration,
             "limitations": result["limitations"], "model": model}
    if mode == "lesion":
        saved["checkpoint_sha256"] = checkpoint_hash
    if mode == "vessel_region_experimental":
        saved.update({"region_component_count": result["region_component_count"],
                      "width_measurements": result["width_measurements"],
                      "minimum_estimated_vessel_region_width_px": result["minimum_estimated_vessel_region_width_px"],
                      "width_unit": result["width_unit"], "width_semantics": result["width_semantics"],
                      "width_quality_notes": result["width_quality_notes"]})
    row = StenosisAnalysis(id=analysis_id, case_id=case.id, image_id=image.id, initiated_by_id=user.id,
                           model_name=checkpoint.name, model_architecture=model.get("resolved_architecture"),
                           status="completed", result_json=json.dumps(saved), artifacts_json=json.dumps(artifact_names))
    db.add(row)
    case.analysis_status = "segmentation_completed"
    case.model_version = f"{mode}:{model.get('architecture') or checkpoint.name}"
    record_audit(db, "segmentation.completed", actor_id=user.id, resource_type="stenosis_analysis", resource_id=analysis_id)
    db.commit()
    db.refresh(row)
    return _output(row)


@router.get("/api/cases/{case_id}/analyses")
def case_analyses(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = case_service.get_accessible_case(db, user, case_id)
    rows = db.scalars(select(StenosisAnalysis).where(StenosisAnalysis.case_id == case.id).order_by(StenosisAnalysis.created_at.desc())).all()
    return [_output(row) for row in rows]


@router.get("/api/analyses/{analysis_id}")
def get_analysis(analysis_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(StenosisAnalysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    case_service.get_accessible_case(db, user, row.case_id)
    return _output(row)


@router.get("/api/analyses")
def recent_analyses(
    response: Response,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, max_length=100),
    mode: str = Query(default="all", pattern="^(all|lesion|vessel_region_experimental)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    visible_ids = case_repo.visible_case_ids(db, user)
    stmt = (
        select(StenosisAnalysis)
        .options(selectinload(StenosisAnalysis.case))
        .where(StenosisAnalysis.case_id.in_(visible_ids))
    )
    needle = (search or "").strip()
    if needle:
        pattern = f"%{needle}%"
        stmt = stmt.join(Case, Case.id == StenosisAnalysis.case_id).where(
            or_(
                StenosisAnalysis.id.ilike(pattern),
                StenosisAnalysis.model_name.ilike(pattern),
                Case.case_identifier.ilike(pattern),
            )
        )
    rows = db.scalars(stmt.order_by(StenosisAnalysis.created_at.desc(), StenosisAnalysis.id)).all()
    data = []
    for row in rows:
        item = _output(row)
        item["case_identifier"] = row.case.case_identifier
        data.append(item)
    if mode != "all":
        data = [item for item in data if item.get("analysis_mode", "lesion") == mode]
    total = len(data)
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page-Limit"] = str(limit)
    response.headers["X-Page-Offset"] = str(offset)
    return data[offset:offset + limit]


@router.get("/api/analyses/{analysis_id}/artifacts/{name}")
def get_artifact(analysis_id: str, name: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(StenosisAnalysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    case_service.get_accessible_case(db, user, row.case_id)
    filename = json.loads(row.artifacts_json).get(name)
    if filename is None:
        raise HTTPException(status_code=404, detail="Analysis artifact not found.")
    path = resolve_inside(_analysis_dir(), filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Analysis artifact file is missing.")
    return FileResponse(path, media_type="image/png", filename=f"{name}.png")


@router.post("/api/analyses/{analysis_id}/ground-truth")
def compare_analysis_to_ground_truth(
    analysis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.DATASET_INSPECT)),
):
    """Compare a stored lesion prediction to an exact train-split COCO match."""
    row = db.get(StenosisAnalysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    case_service.get_accessible_case(db, user, row.case_id)
    saved = json.loads(row.result_json)
    if saved.get("analysis_mode", "lesion") != "lesion":
        raise HTTPException(status_code=409, detail="Ground-truth comparison supports lesion analyses only.")
    stored_checkpoint_hash = saved.get("checkpoint_sha256")
    checkpoint = _model_path()
    if not stored_checkpoint_hash or row.model_name != checkpoint.name:
        raise HTTPException(status_code=409, detail="This analysis lacks verifiable identity for the active model checkpoint.")
    if not checkpoint.is_file() or _sha256_file(checkpoint) != stored_checkpoint_hash:
        raise HTTPException(status_code=409, detail="The existing prediction checkpoint is missing or differs from the recorded checkpoint.")
    image_row = db.get(UploadedImage, row.image_id)
    if image_row is None:
        raise HTTPException(status_code=404, detail="Stored source image record is missing.")
    source = image_service.original_path(image_row)
    try:
        record, annotations, _dataset_path, image_digest = find_exact_training_annotation(
            source, image_row.original_filename, stenosis_split_dir("train"),
        )
        if image_row.width != record["width"] or image_row.height != record["height"]:
            raise ValueError("Uploaded image metadata dimensions do not align with its exact COCO image record.")
        if not annotations:
            raise ValueError("The matched training image has no category-26 stenosis annotation.")
        with Image.open(source) as opened:
            image_rgb = np.asarray(opened.convert("RGB"))
        if image_rgb.shape[:2] != (record["height"], record["width"]):
            raise ValueError("Uploaded and COCO dimensions do not align.")
        truth = np.asarray(rasterize_polygons(record["width"], record["height"], annotations)) > 0
        if not truth.any():
            raise ValueError("The matched category-26 polygons did not produce a valid foreground mask.")
        artifacts = json.loads(row.artifacts_json)
        mask_name = artifacts.get("mask")
        if not mask_name:
            raise ValueError("This analysis has no stored prediction mask artifact.")
        mask_path = resolve_inside(_analysis_dir(), mask_name)
        prediction_u8 = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if prediction_u8 is None or prediction_u8.shape != truth.shape:
            raise ValueError("Stored prediction mask is missing or does not align with the COCO image dimensions.")
        metrics, components = evaluate_masks(truth, prediction_u8 > 0, saved.get("candidates", []))
        comparison = comparison_visualization(image_rgb, truth, prediction_u8 > 0)
        ok, encoded = cv2.imencode(".png", comparison)
        if not ok:
            raise RuntimeError("Could not encode the ground-truth comparison visualization.")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Ground-truth comparison failed.")
        raise HTTPException(status_code=503, detail=f"Ground-truth comparison failed ({type(exc).__name__}).") from exc

    model_hash = stored_checkpoint_hash
    comparison_result = {
        "dataset_split": "stenosis/train",
        "annotation_file": "stenosis/train/annotations/train.json",
        "dataset_image_file": f"stenosis/train/images/{record['file_name']}",
        "image_id": record["id"],
        "annotation_ids": [int(item["id"]) for item in annotations],
        "category_ids": sorted({int(item["category_id"]) for item in annotations}),
        "width": record["width"], "height": record["height"],
        "image_sha256": image_digest,
        "alignment_verified": True,
        "checkpoint_name": row.model_name,
        "checkpoint_sha256": model_hash,
        "checkpoint_identity_verified": model_hash is not None,
        "checkpoint_matches_current": True,
        "prediction_source": "existing persisted mask; model was not rerun",
        "metrics_semantics": "pixel overlap with ARCADE category-26 lesion polygons; not lumen or clinical stenosis metrics",
        "metrics": metrics,
        "predicted_components": components,
    }
    filename = f"{row.id}_ground_truth_comparison.png"
    resolve_inside(_analysis_dir(), filename).write_bytes(encoded.tobytes())
    artifacts["ground_truth_comparison"] = filename
    saved["ground_truth_comparison"] = comparison_result
    row.result_json = json.dumps(saved)
    row.artifacts_json = json.dumps(artifacts)
    record_audit(db, "analysis.ground_truth_compared", actor_id=user.id,
                 resource_type="stenosis_analysis", resource_id=row.id)
    db.commit()
    db.refresh(row)
    return _output(row)


@router.post("/api/analyses/{analysis_id}/explain")
def explain_analysis(analysis_id: str, db: Session = Depends(get_db),
                     user: User = Depends(require_permission(Permission.IMAGE_PREPROCESS))):
    """Generate an optional Integrated Gradients image for a stored lesion analysis."""
    row = db.get(StenosisAnalysis, analysis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    case_service.get_accessible_case(db, user, row.case_id)
    saved = json.loads(row.result_json)
    if saved.get("analysis_mode", "lesion") != "lesion":
        raise HTTPException(status_code=409, detail="Attribution is supported only for lesion segmentation analyses.")
    checkpoint = _model_path()
    expected_hash = saved.get("checkpoint_sha256")
    if not expected_hash:
        raise HTTPException(status_code=409, detail="This legacy analysis has no recorded checkpoint hash; a same-model explanation cannot be verified.")
    if not checkpoint.is_file() or _sha256_file(checkpoint) != expected_hash:
        raise HTTPException(status_code=409, detail="The active checkpoint differs from the one used for this analysis.")
    image_row = db.get(UploadedImage, row.image_id)
    if image_row is None:
        raise HTTPException(status_code=404, detail="Stored source image record is missing.")
    source = image_service.original_path(image_row)
    if not source.is_file():
        raise HTTPException(status_code=404, detail="Stored source image file is missing.")
    try:
        loaded = load_image(source)
        arr = loaded.array
        if arr.ndim == 2:
            bgr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
        elif arr.ndim == 3 and arr.shape[2] == 4:
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        elif arr.ndim == 3 and arr.shape[2] == 3:
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        else:
            raise ValueError("Unsupported source image layout.")
        if bgr.dtype != np.uint8:
            finite = np.nan_to_num(bgr.astype(np.float32), copy=False)
            low, high = float(finite.min()), float(finite.max())
            bgr = np.zeros(finite.shape, dtype=np.uint8) if high <= low else np.clip((finite - low) * (255 / (high - low)), 0, 255).astype(np.uint8)
        with _model_lock:
            analyzer = _load_analyzer(str(checkpoint.resolve()))
            if _sha256_file(checkpoint) != expected_hash:
                raise HTTPException(status_code=409, detail="The active checkpoint changed while preparing attribution.")
            heat, metadata = integrated_gradients_attribution(
                analyzer.model, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), analyzer.image_size,
                analyzer.device, analyzer.meta.get("normalization", "none"), analyzer.threshold,
            )
        content = encode_png(attribution_heatmap(bgr, heat))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Attribution unavailable: {exc}") from exc
    except Exception as exc:
        logger.exception("Integrated Gradients attribution failed.")
        raise HTTPException(status_code=503, detail=f"Attribution could not be generated ({type(exc).__name__}).") from exc
    filename = f"{row.id}_integrated_gradients.png"
    resolve_inside(_analysis_dir(), filename).write_bytes(content)
    artifacts = json.loads(row.artifacts_json)
    artifacts["integrated_gradients"] = filename
    saved["explainability"] = {**metadata, "checkpoint_sha256": expected_hash}
    row.artifacts_json = json.dumps(artifacts)
    row.result_json = json.dumps(saved)
    record_audit(db, "segmentation.explanation_generated", actor_id=user.id,
                 resource_type="stenosis_analysis", resource_id=row.id)
    db.commit()
    db.refresh(row)
    return _output(row)


def _case_report(case_id: str, db: Session, user: User) -> list[dict]:
    case = case_service.get_accessible_case(db, user, case_id)
    rows = db.scalars(
        select(StenosisAnalysis)
        .options(
            selectinload(StenosisAnalysis.case),
            selectinload(StenosisAnalysis.image).selectinload(UploadedImage.preprocessing_runs),
        )
        .where(StenosisAnalysis.case_id == case.id)
        .order_by(StenosisAnalysis.created_at.desc())
    ).all()
    records = []
    for row in rows:
        image = row.image
        preprocessing = max(
            image.preprocessing_runs if image else [],
            key=lambda run: run.started_at.isoformat() if run.started_at else "",
            default=None,
        )
        preprocessing_data = None
        if preprocessing:
            try:
                operations = json.loads(preprocessing.operations_json)
            except (TypeError, json.JSONDecodeError):
                operations = None
            try:
                configuration = json.loads(preprocessing.config_json)
            except (TypeError, json.JSONDecodeError):
                configuration = None
            preprocessing_data = {
                "id": preprocessing.id,
                "status": preprocessing.status,
                "started_at": preprocessing.started_at.isoformat() if preprocessing.started_at else None,
                "completed_at": preprocessing.completed_at.isoformat() if preprocessing.completed_at else None,
                "operations": operations,
                "configuration": configuration,
            }
        records.append({
            "case_id": case.id,
            "case_identifier": case.case_identifier,
            "case_name": case.case_identifier,
            "patient_identifier": case.patient_identifier,
            "image": {
                "id": image.id if image else row.image_id,
                "filename": image.original_filename if image else None,
                "width": image.width if image else None,
                "height": image.height if image else None,
                "format": image.format if image else None,
            },
            "preprocessing": preprocessing_data,
            "analysis_architecture": row.model_architecture,
            "analysis": _output(row),
        })
    return records


def _simple_pdf(lines: list[str]) -> bytes:
    """Create a small dependency-free PDF report using the built-in Helvetica font."""
    wrapped_lines = []
    for line in lines:
        clean = line.encode("ascii", "replace").decode("ascii")
        wrapped_lines.extend(textwrap.wrap(clean, width=96, break_long_words=True, break_on_hyphens=False) or [""])
    pages = [wrapped_lines[index:index + 32] for index in range(0, max(1, len(wrapped_lines)), 32)]
    objects: list[bytes] = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    page_refs = []
    for page_lines in pages:
        page_number = len(objects) + 1
        content_number = page_number + 1
        page_refs.append(f"{page_number} 0 R")
        commands = ["BT", "/F1 10 Tf", "50 750 Td"]
        for index, line in enumerate(page_lines):
            clean = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            if index:
                commands.append("0 -20 Td")
            commands.append(f"({clean}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("ascii")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_number} 0 R >>".encode("ascii"))
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(page_refs)} >>".encode("ascii")
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, item in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii")); output.extend(item); output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(output)


@router.get("/api/cases/{case_id}/reports/{format}")
def export_case_report(case_id: str, format: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    records = _case_report(case_id, db, user)
    if format == "json":
        return records
    flat = []
    for record in records:
        analysis = record["analysis"]
        measurement = analysis.get("diameter_measurement") or DIAMETER_MEASUREMENT_UNAVAILABLE
        candidates = analysis.get("candidates") or [None]
        model = analysis.get("model", {})
        validation = model.get("validation", {})
        macro = validation.get("metrics", {}).get("per_image_macro", {})
        # Older persisted analyses predate the nested validation report and keep
        # the checkpoint's stored scores directly on the model metadata object.
        validation_dice = macro.get("dice")
        if validation_dice is None:
            validation_dice = model.get("val_dice")
        validation_iou = macro.get("iou")
        if validation_iou is None:
            validation_iou = model.get("val_iou")
        for candidate in candidates:
            candidate = candidate or {}
            calibration = analysis.get("image_calibration") or {}
            image = record.get("image") or {}
            preprocessing = record.get("preprocessing") or {}
            ground_truth = analysis.get("ground_truth_comparison") or {}
            ground_truth_metrics = ground_truth.get("metrics") or {}
            flat.append({
                "analysis_id": analysis["id"],
                "case_id": record["case_id"],
                "case_identifier": record["case_identifier"],
                "case_name": record["case_name"],
                "image_id": image.get("id"),
                "image_filename": image.get("filename"),
                "image_width": image.get("width"),
                "image_height": image.get("height"),
                "image_format": image.get("format"),
                "analysis_mode": analysis.get("analysis_mode", "lesion"),
                "target_semantics": analysis.get("target_semantics"),
                "analysis_date": analysis["created_at"],
                "created_at": analysis["created_at"],
                "status": analysis.get("status"),
                "model_name": analysis["model_name"],
                "checkpoint": analysis["model_name"],
                "checkpoint_sha256": analysis.get("checkpoint_sha256"),
                "model_architecture": record.get("analysis_architecture") or model.get("architecture") or model.get("resolved_architecture"),
                "architecture": record.get("analysis_architecture") or model.get("architecture") or model.get("resolved_architecture"),
                "threshold": analysis.get("threshold"),
                "foreground_pixels": analysis.get("foreground_pixels"),
                "candidate_count": analysis.get("candidate_count"),
                "min_component_area": analysis.get("min_area"),
                "preprocessing_run_id": preprocessing.get("id"),
                "preprocessing_status": preprocessing.get("status"),
                "preprocessing_started_at": preprocessing.get("started_at"),
                "preprocessing_completed_at": preprocessing.get("completed_at"),
                "preprocessing_operations": json.dumps(preprocessing.get("operations"), separators=(",", ":")) if preprocessing.get("operations") is not None else None,
                "preprocessing_configuration": json.dumps(preprocessing.get("configuration"), separators=(",", ":")) if preprocessing.get("configuration") is not None else None,
                "candidate_id": candidate.get("id"), "x": candidate.get("x"), "y": candidate.get("y"),
                "width": candidate.get("width"), "height": candidate.get("height"),
                "pixel_area": candidate.get("pixel_area"),
                "predicted_probability": candidate.get("mean_predicted_probability", candidate.get("confidence")),
                "validation_split": validation.get("split"), "validation_samples": validation.get("samples"),
                "validation_macro_dice": validation_dice, "validation_macro_iou": validation_iou,
                "explainability_method": (analysis.get("explainability") or {}).get("method"),
                "explainability_steps": (analysis.get("explainability") or {}).get("steps"),
                "ground_truth_split": ground_truth.get("dataset_split"),
                "ground_truth_image_id": ground_truth.get("image_id"),
                "ground_truth_annotation_ids": json.dumps(ground_truth.get("annotation_ids", []), separators=(",", ":")),
                "ground_truth_category_ids": json.dumps(ground_truth.get("category_ids", []), separators=(",", ":")),
                "ground_truth_dice": ground_truth_metrics.get("dice"),
                "ground_truth_iou": ground_truth_metrics.get("iou"),
                "ground_truth_precision": ground_truth_metrics.get("precision"),
                "ground_truth_recall": ground_truth_metrics.get("recall"),
                "ground_truth_tp": ground_truth_metrics.get("tp"),
                "ground_truth_fp": ground_truth_metrics.get("fp"),
                "ground_truth_fn": ground_truth_metrics.get("fn"),
                "candidate_ground_truth_overlap_pixels": next((component.get("ground_truth_overlap_pixels") for component in ground_truth.get("predicted_components", []) if component.get("candidate_id") == candidate.get("id")), None),
                "candidate_overlaps_ground_truth": next((component.get("overlaps_ground_truth") for component in ground_truth.get("predicted_components", []) if component.get("candidate_id") == candidate.get("id")), None),
                "measurement_status": measurement.get("measurement_status", "unavailable"),
                "reference_vessel_diameter_mm": measurement.get("reference_vessel_diameter_mm"),
                "minimum_lumen_diameter_mm": measurement.get("minimum_lumen_diameter_mm"),
                "reference_vessel_diameter_px": measurement.get("reference_vessel_diameter_px"),
                "minimum_lumen_diameter_px": measurement.get("minimum_lumen_diameter_px"),
                "measurement_location": measurement.get("measurement_location"),
                "pixel_spacing_status": calibration.get("status", "unavailable"),
                "pixel_spacing_source": calibration.get("source"),
                "row_spacing_mm_per_pixel": calibration.get("row_spacing_mm_per_pixel"),
                "column_spacing_mm_per_pixel": calibration.get("column_spacing_mm_per_pixel"),
                "pixel_spacing_calibration_type": calibration.get("calibration_type"),
                "pixel_spacing_used_for_measurement": calibration.get("used_for_measurement", False),
                "severity": None, "percentage_narrowing": analysis.get("percentage_narrowing"),
                "region_component_count": analysis.get("region_component_count"),
                "minimum_estimated_vessel_region_width_px": analysis.get("minimum_estimated_vessel_region_width_px"),
                "width_unit": analysis.get("width_unit"),
                "width_measurements": json.dumps(analysis.get("width_measurements", []), separators=(",", ":")),
                "artifact_urls": json.dumps(analysis.get("artifacts", {}), separators=(",", ":")),
            })
    if format == "csv":
        output = io.StringIO(newline="")
        fields = ["analysis_id", "case_id", "case_identifier", "case_name", "image_id", "image_filename", "image_width", "image_height", "image_format",
                  "analysis_date", "created_at", "analysis_mode", "status", "model_name", "checkpoint", "checkpoint_sha256", "model_architecture", "architecture", "target_semantics", "threshold",
                  "foreground_pixels", "candidate_count", "min_component_area", "preprocessing_run_id", "preprocessing_status", "preprocessing_started_at", "preprocessing_completed_at", "preprocessing_operations", "preprocessing_configuration",
                  "candidate_id", "x", "y", "width", "height", "pixel_area", "predicted_probability",
                  "validation_split", "validation_samples", "validation_macro_dice", "validation_macro_iou",
                  "explainability_method", "explainability_steps",
                  "ground_truth_split", "ground_truth_image_id", "ground_truth_annotation_ids", "ground_truth_category_ids",
                  "ground_truth_dice", "ground_truth_iou", "ground_truth_precision", "ground_truth_recall",
                  "ground_truth_tp", "ground_truth_fp", "ground_truth_fn", "candidate_ground_truth_overlap_pixels",
                  "candidate_overlaps_ground_truth",
                  "measurement_status", "reference_vessel_diameter_mm", "minimum_lumen_diameter_mm",
                  "reference_vessel_diameter_px", "minimum_lumen_diameter_px",
                  "measurement_location", "pixel_spacing_status", "pixel_spacing_source",
                  "row_spacing_mm_per_pixel", "column_spacing_mm_per_pixel", "pixel_spacing_calibration_type",
                  "pixel_spacing_used_for_measurement", "severity", "percentage_narrowing", "region_component_count",
                  "minimum_estimated_vessel_region_width_px", "width_unit", "width_measurements", "artifact_urls"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(flat)
        return StreamingResponse(iter(["\ufeff" + output.getvalue()]), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f"attachment; filename=case-{case_id}-report.csv"})
    if format == "pdf":
        lines = ["Artery segmentation research report", f"Case: {case_id}", "Research output only; not a diagnosis.",
                 "Diameter-based stenosis measurement: Unable to calculate.",
                 "Reference vessel diameter: unavailable mm; minimum lumen diameter: unavailable mm; measurement location: unavailable.",
                 "Reason: no validated lumen boundaries, reference cross-section, and physical calibration are available.",
                 "Clinical severity is unavailable.",
                 "Probability overlays/heatmaps are not Grad-CAM or clinical confidence."]
        for record in records:
            analysis = record["analysis"]
            model = analysis.get("model", {})
            image = record.get("image") or {}
            preprocessing = record.get("preprocessing") or {}
            calibration = analysis.get("image_calibration") or {}
            lines.append(f"Case identifier: {record.get('case_identifier', 'unavailable')}")
            lines.append(
                f"Image: {image.get('filename') or 'unavailable'} | {image.get('width') or 'unavailable'} x "
                f"{image.get('height') or 'unavailable'} | {image.get('format') or 'unavailable'}"
            )
            if preprocessing:
                lines.append(
                    f"Preprocessing: {preprocessing.get('status', 'unavailable')} | "
                    f"operations={json.dumps(preprocessing.get('operations'), ensure_ascii=True)} | "
                    f"configuration={json.dumps(preprocessing.get('configuration'), ensure_ascii=True)}"
                )
            else:
                lines.append("Preprocessing: unavailable for the analyzed image.")
            lines.append(f"Analysis mode: {analysis.get('analysis_mode', 'lesion')} | target: {analysis.get('target_semantics', 'category-26 lesion region')}")
            if calibration.get("row_spacing_mm_per_pixel") is not None:
                lines.append(
                    "DICOM PixelSpacing reported row/column mm per pixel: "
                    f"{calibration['row_spacing_mm_per_pixel']}/{calibration['column_spacing_mm_per_pixel']}; "
                    "not validated or used for lumen measurements."
                )
            else:
                lines.append(f"Image calibration: unavailable ({calibration.get('reason', 'no calibration metadata')})")
            if analysis.get("analysis_mode") == "vessel_region_experimental":
                lines.append("Experimental SYNTAX vessel-region widths are pixel estimates, not lumen diameters or stenosis measurements.")
                lines.append(f"Estimated width samples: {len(analysis.get('width_measurements', []))} | smallest sampled region width px={analysis.get('minimum_estimated_vessel_region_width_px')}")
                for index, item in enumerate(analysis.get("width_measurements", [])[:24], start=1):
                    lines.append(f"Width section {index}: {item.get('width_px')} px at x={item.get('x')} y={item.get('y')} axis={item.get('vessel_axis_angle_degrees')} degrees")
            validation = model.get("validation", {})
            macro = validation.get("metrics", {}).get("per_image_macro", {})
            architecture = record.get("analysis_architecture") or model.get("architecture") or model.get("resolved_architecture") or "unavailable"
            lines.append(
                f"Analysis {analysis['id']} | {analysis['created_at']} | {analysis['model_name']} | "
                f"{architecture} | threshold {analysis['threshold']}"
            )
            lines.append(
                f"Model details: epoch={model.get('epoch', 'unavailable')} | input size={model.get('image_size', 'unavailable')} | "
                f"device={model.get('device', 'unavailable')} | checkpoint SHA-256={analysis.get('checkpoint_sha256') or 'unavailable'}"
            )
            validation_dice = macro.get("dice")
            if validation_dice is None:
                validation_dice = model.get("val_dice")
            validation_iou = macro.get("iou")
            if validation_iou is None:
                validation_iou = model.get("val_iou")
            explanation = analysis.get("explainability") or {}
            if explanation:
                lines.append(f"Input attribution: {explanation.get('method')} | steps={explanation.get('steps')} | relative sensitivity only; not clinical confidence or validated diagnostic evidence.")
            comparison = analysis.get("ground_truth_comparison") or {}
            comparison_metrics = comparison.get("metrics") or {}
            if comparison:
                lines.append(f"ARCADE pixel comparison: {comparison.get('dataset_split')} image_id={comparison.get('image_id')} annotations={comparison.get('annotation_ids')} category_ids={comparison.get('category_ids')} | Dice={comparison_metrics.get('dice')} IoU={comparison_metrics.get('iou')} precision={comparison_metrics.get('precision')} recall={comparison_metrics.get('recall')} TP={comparison_metrics.get('tp')} FP={comparison_metrics.get('fp')} FN={comparison_metrics.get('fn')}")
                for component in comparison.get("predicted_components", []):
                    lines.append(f"Candidate {component.get('candidate_id')} ground-truth overlap={component.get('ground_truth_overlap_pixels')} px; overlaps={component.get('overlaps_ground_truth')}")
                lines.append("Metrics compare category-26 lesion pixels only; they are not lumen measurements or clinical stenosis percentages.")
            if validation_dice is not None or validation_iou is not None:
                if validation.get("split") or validation.get("samples") is not None:
                    lines.append(
                        f"Validation {validation.get('split') or 'split unavailable'} "
                        f"n={validation.get('samples') if validation.get('samples') is not None else 'unavailable'} | "
                        f"macro Dice {validation_dice if validation_dice is not None else 'unavailable'} | "
                        f"macro IoU {validation_iou if validation_iou is not None else 'unavailable'} | "
                        f"origin={model.get('validation_metric_origin', 'saved validation report')}"
                    )
                else:
                    lines.append(
                        f"Stored checkpoint validation metrics | Dice {validation_dice if validation_dice is not None else 'unavailable'} | "
                        f"IoU {validation_iou if validation_iou is not None else 'unavailable'} | "
                        "split/sample provenance unavailable"
                    )
            measurement = analysis.get("diameter_measurement", {})
            if not measurement:
                measurement = DIAMETER_MEASUREMENT_UNAVAILABLE
            reference_mm = measurement.get("reference_vessel_diameter_mm")
            minimum_mm = measurement.get("minimum_lumen_diameter_mm")
            percentage = analysis.get("percentage_narrowing")
            lines.append(
                f"Diameter measurement {measurement.get('measurement_status', 'unavailable')} | "
                f"reference mm={reference_mm if reference_mm is not None else 'unavailable'} | "
                f"minimum lumen mm={minimum_mm if minimum_mm is not None else 'unavailable'} | "
                f"narrowing percent={percentage if percentage is not None else 'unavailable'}"
            )
            lines.append(
                f"Pixel diameters | reference px={measurement.get('reference_vessel_diameter_px', 'unavailable')} | "
                f"minimum lumen px={measurement.get('minimum_lumen_diameter_px', 'unavailable')} | "
                f"quality={measurement.get('quality', 'unavailable')}"
            )
            for candidate in analysis.get("candidates", []):
                probability = candidate.get("mean_predicted_probability", candidate.get("confidence"))
                lines.append(f"Candidate {candidate.get('id')} bbox x={candidate.get('x')} y={candidate.get('y')} w={candidate.get('width')} h={candidate.get('height')} area_px={candidate.get('pixel_area')} mean_predicted_p={probability}")
        return Response(_simple_pdf(lines), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=case-{case_id}-report.pdf"})
    raise HTTPException(status_code=400, detail="Format must be pdf, csv, or json.")
