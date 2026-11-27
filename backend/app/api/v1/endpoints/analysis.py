import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from PIL import Image, UnidentifiedImageError

from app.api.deps import get_current_user, owned_or_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.models.analysis_run import AnalysisRun
from app.models.case import Case
from app.models.image import MedicalImage
from app.models.user import User
from app.schemas.analysis import AnalysisRunCreate, AnalysisRunRead
from app.services.analysis_inference import InferenceUnavailable, inference_worker
from app.services.severity_assessment import assess_saved_percentage_narrowing
from app.services.analysis_storage import (
    ARTIFACT_MEDIA_TYPES,
    cleanup_analysis_run_directory,
    create_analysis_run_directory,
    render_legacy_combined_visualization,
    resolve_analysis_artifact_path,
    validate_artifact_manifest,
)
from app.services.storage import FORMATS, resolve_storage_path

router = APIRouter(tags=["analysis"])
logger = logging.getLogger(__name__)


def _owned_run_query(run_id: UUID, current_user: User):
    query = select(AnalysisRun).join(Case, Case.id == AnalysisRun.case_id).where(AnalysisRun.id == run_id)
    if current_user.role != "admin":
        query = query.where(Case.owner_id == current_user.id)
    return query


@router.post("/cases/{case_id}/analysis-runs", response_model=AnalysisRunRead, status_code=status.HTTP_201_CREATED)
def start_analysis(
    case_id: UUID,
    body: AnalysisRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalysisRun:
    case = db.scalar(owned_or_admin(select(Case), Case, current_user).where(Case.id == case_id))
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    image = db.scalar(select(MedicalImage).where(MedicalImage.id == body.image_id, MedicalImage.case_id == case.id))
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found in this case")

    run = AnalysisRun(
        case_id=case.id,
        image_id=image.id,
        requested_by_id=current_user.id,
        status="processing",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    started = time.perf_counter()
    settings = get_settings()
    run_directory: Path | None = None
    try:
        try:
            image_path = resolve_storage_path(settings.upload_directory, image.storage_key)
        except ValueError as exc:
            raise InferenceUnavailable("Stored source image path is invalid") from exc
        if not image_path.is_file():
            raise InferenceUnavailable("Stored source image is unavailable")
        if image_path.stat().st_size > settings.max_upload_size_bytes:
            raise InferenceUnavailable("Stored source image exceeds the configured size limit")
        try:
            with Image.open(image_path) as source_image:
                expected_size = source_image.size
                expected_format = FORMATS.get(image_path.suffix.lower())
                if (
                    expected_format is None
                    or source_image.format != expected_format[0]
                    or expected_format[1] != image.media_type
                    or expected_size[0] * expected_size[1] > settings.max_image_pixels
                ):
                    raise InferenceUnavailable("Stored source image is not a supported image")
                source_image.verify()
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise InferenceUnavailable("Stored source image is unreadable") from exc

        run_directory = create_analysis_run_directory(settings.analysis_output_directory, run.id)
        response = inference_worker.run(image_path, run_directory, run.id, settings)
        if tuple(response["original_size"]) != tuple(expected_size):
            raise InferenceUnavailable("Inference response dimensions differ from the source image")
        artifacts = validate_artifact_manifest(
            settings.analysis_output_directory,
            run.id,
            response["artifacts"],
            expected_image_size=expected_size,
        )
        candidates = response["candidates"]
        severity_assessment = assess_saved_percentage_narrowing(
            response.get("percentage_narrowing"),
            candidates,
        )
        metadata = {
            "schema_version": 1,
            "models": response["metadata"],
            "model_times": response["model_times"],
            "original_size": response["original_size"],
            "candidate_label": "Predicted stenosis candidates; not confirmed stenoses",
            "candidates": candidates,
            "percentage_narrowing": response["percentage_narrowing"],
            "severity_assessment": severity_assessment,
            "artifacts": artifacts,
            "clinical_measurements_generated": False,
            "clinical_validation": False,
        }
        # Reject non-JSON values before marking a run complete.
        json.dumps(metadata, allow_nan=False)
        run.result_metadata = metadata
        run.duration_seconds = time.perf_counter() - started
        run.completed_at = datetime.now(timezone.utc)
        run.status = "completed"
        run.failure_code = None
        run.failure_message = None
        db.commit()
        db.refresh(run)
    except Exception as exc:
        # Do not log exception text or a traceback: inference failures may include
        # local paths or details derived from private image processing.
        logger.error(
            "Synchronous analysis failed (run_id=%s, exception_type=%s)",
            run.id,
            type(exc).__name__,
        )
        db.rollback()
        run = db.get(AnalysisRun, run.id)
        if run is None:
            raise
        if run_directory is not None:
            cleanup_analysis_run_directory(settings.analysis_output_directory, run.id)
        run.status = "failed"
        run.duration_seconds = time.perf_counter() - started
        run.completed_at = datetime.now(timezone.utc)
        run.result_metadata = None
        run.failure_code = "inference_failed"
        run.failure_message = "Analysis could not be completed. The source image and existing records were preserved."
        db.commit()
        db.refresh(run)
    return run


@router.get("/cases/{case_id}/analysis-runs", response_model=list[AnalysisRunRead])
def list_case_analysis_runs(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AnalysisRun]:
    case = db.scalar(owned_or_admin(select(Case), Case, current_user).where(Case.id == case_id))
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    query = (
        select(AnalysisRun)
        .where(AnalysisRun.case_id == case.id)
        .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
    )
    return list(db.scalars(query).all())


@router.get("/analysis-runs/{run_id}", response_model=AnalysisRunRead)
def get_analysis_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalysisRun:
    run = db.scalar(_owned_run_query(run_id, current_user))
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    return run


@router.get("/analysis-runs/{run_id}/results")
def get_analysis_results(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    run = db.scalar(_owned_run_query(run_id, current_user))
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")
    if run.status != "completed" or not run.result_metadata:
        return {"run_id": run.id, "status": run.status, "detail": run.failure_message}
    artifacts = run.result_metadata.get("artifacts", {})
    return {
        "run_id": run.id,
        "status": run.status,
        "image_id": run.image_id,
        "source_image_url": f"/api/v1/images/{run.image_id}/content" if run.image_id else None,
        "metadata": {key: value for key, value in run.result_metadata.items() if key != "artifacts"},
        "artifacts": {
            filename: f"/api/v1/analysis-runs/{run.id}/artifacts/{filename}"
            for filename in artifacts
            if filename in ARTIFACT_MEDIA_TYPES
        },
    }


@router.get("/analysis-runs/{run_id}/artifacts/{artifact_name}")
def get_analysis_artifact(
    run_id: UUID,
    artifact_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    run = db.scalar(_owned_run_query(run_id, current_user))
    if run is None or run.status != "completed" or not run.result_metadata:
        raise HTTPException(status_code=404, detail="Analysis artifact not found")
    artifacts = run.result_metadata.get("artifacts", {})
    relative_key = artifacts.get(artifact_name) if isinstance(artifacts, dict) else None
    if artifact_name not in ARTIFACT_MEDIA_TYPES or relative_key is None:
        raise HTTPException(status_code=404, detail="Analysis artifact not found")
    try:
        path = resolve_analysis_artifact_path(get_settings().analysis_output_directory, run.id, relative_key)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Analysis artifact not found") from None
    if artifact_name == "combined_visualization.png":
        repaired = render_legacy_combined_visualization(path)
        if repaired is not None:
            return Response(
                content=repaired,
                media_type=ARTIFACT_MEDIA_TYPES[artifact_name],
                headers={
                    "Content-Disposition": 'inline; filename="combined_visualization.png"',
                    "Cache-Control": "private, no-store",
                },
            )
    return FileResponse(
        path,
        media_type=ARTIFACT_MEDIA_TYPES[artifact_name],
        filename=artifact_name,
        headers={"Cache-Control": "private, no-store"},
    )
