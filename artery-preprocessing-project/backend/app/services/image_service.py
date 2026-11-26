import json
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.case import Case
from app.models.image import UploadedImage
from app.models.preprocessing import PreprocessingRun
from app.models.user import User
from app.preprocessing.exceptions import ImageValidationError, PreprocessingParameterError, UnsupportedImageError
from app.preprocessing.pipeline import load_image, preprocess_image, validate_image
from app.schemas.preprocessing import PreprocessRequest
from app.utils.audit import record_audit
from app.utils.files import resolve_inside, sanitize_original_filename, unique_storage_name


def _safe_user_error(exc: Exception) -> str:
    if isinstance(exc, (ImageValidationError, UnsupportedImageError, PreprocessingParameterError)):
        return str(exc)
    return "The image could not be processed."


def upload_image(db: Session, user: User, case: Case, file: UploadFile) -> UploadedImage:
    settings = get_settings()
    original_name = sanitize_original_filename(file.filename or "upload")
    storage_name = unique_storage_name(original_name)
    upload_dir = settings.resolved_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = resolve_inside(upload_dir, storage_name)

    size = 0
    try:
        with dest.open("wb") as buffer:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    buffer.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File exceeds the configured size limit.",
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload failed.") from exc

    try:
        validate_image(dest, settings.max_upload_bytes)
        loaded = load_image(dest)
    except (ImageValidationError, UnsupportedImageError) as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_safe_user_error(exc)) from exc

    image = UploadedImage(
        case_id=case.id,
        original_filename=original_name,
        storage_filename=storage_name,
        format=loaded.format,
        file_size=size,
        width=loaded.width,
        height=loaded.height,
        metadata_json=json.dumps(loaded.metadata, default=str),
        uploaded_by_id=user.id,
    )
    case.analysis_status = "image_uploaded"
    db.add(image)
    db.flush()
    record_audit(db, "image.upload", actor_id=user.id, resource_type="image", resource_id=image.id)
    db.commit()
    db.refresh(image)
    return image


def original_path(image: UploadedImage) -> Path:
    return resolve_inside(get_settings().resolved_upload_dir(), image.storage_filename)


def processed_path(run: PreprocessingRun) -> Path:
    if not run.processed_storage_filename:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No processed image is available.")
    return resolve_inside(get_settings().resolved_processed_dir(), run.processed_storage_filename)


def run_preprocessing(db: Session, user: User, case: Case, params: PreprocessRequest) -> PreprocessingRun:
    if not case.images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload an image before preprocessing.")
    image = sorted(case.images, key=lambda item: item.uploaded_at, reverse=True)[0]
    source = original_path(image)
    settings = get_settings()
    processed_name = unique_storage_name("processed.png").rsplit(".", 1)[0] + ".png"
    dest = resolve_inside(settings.resolved_processed_dir(), processed_name)

    run = PreprocessingRun(
        case_id=case.id,
        image_id=image.id,
        config_json=params.model_dump_json(),
        input_format=image.format,
        original_width=image.width,
        original_height=image.height,
        operations_json="[]",
        status="running",
        initiated_by_id=user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    original_before = source.read_bytes() if source.exists() else b""
    from datetime import datetime, timezone

    started = datetime.now(timezone.utc)
    try:
        result = preprocess_image(source, dest, settings.max_upload_bytes, params.model_dump())
        if source.read_bytes() != original_before:
            raise RuntimeError("Original image changed during preprocessing.")
        completed = datetime.now(timezone.utc)
        run.status = "completed"
        run.processed_storage_filename = processed_name
        run.processed_width = result["processed_width"]
        run.processed_height = result["processed_height"]
        run.operations_json = json.dumps(result["operations"])
        run.error_message = None
        run.duration_ms = int((completed - started).total_seconds() * 1000)
        run.completed_at = completed
        case.analysis_status = "preprocessed"
    except Exception as exc:
        completed = datetime.now(timezone.utc)
        dest.unlink(missing_ok=True)
        dest.with_suffix(".json").unlink(missing_ok=True)
        run.status = "failed"
        run.error_message = _safe_user_error(exc)
        run.duration_ms = int((completed - started).total_seconds() * 1000)
        run.completed_at = completed
        case.analysis_status = "preprocessing_failed"
        record_audit(
            db,
            "preprocessing.failed",
            actor_id=user.id,
            resource_type="preprocessing_run",
            resource_id=run.id,
        )
        db.commit()
        db.refresh(run)
        if isinstance(exc, (ImageValidationError, UnsupportedImageError, PreprocessingParameterError)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=run.error_message) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=run.error_message) from exc

    record_audit(db, "preprocessing.completed", actor_id=user.id, resource_type="preprocessing_run", resource_id=run.id)
    db.commit()
    db.refresh(run)
    return run


def remove_case_files(case: Case) -> None:
    settings = get_settings()
    for image in case.images:
        path = resolve_inside(settings.resolved_upload_dir(), image.storage_filename)
        path.unlink(missing_ok=True)
    for run in case.preprocessing_runs:
        if run.processed_storage_filename:
            path = resolve_inside(settings.resolved_processed_dir(), run.processed_storage_filename)
            path.unlink(missing_ok=True)
            path.with_suffix(".json").unlink(missing_ok=True)
    from app.core.config import get_settings
    from app.models.analysis import StenosisAnalysis
    import json

    analysis_dir = get_settings().resolved_analysis_dir()
    for analysis in case.stenosis_analyses:
        for filename in json.loads(analysis.artifacts_json).values():
            resolve_inside(analysis_dir, filename).unlink(missing_ok=True)


