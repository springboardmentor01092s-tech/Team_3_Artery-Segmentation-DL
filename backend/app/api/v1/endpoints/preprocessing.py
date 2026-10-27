from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.case import Case
from app.models.image import MedicalImage
from app.models.image_preprocessing import ImagePreprocessing
from app.models.user import User
from app.schemas.preprocessing import PreprocessingMetadata, PreprocessingRead
from app.services.preprocessing import PreprocessingError, preprocess_image_file
from app.services.storage import resolve_storage_path

router = APIRouter(tags=["image preprocessing"])
COMPLETED_MESSAGE = "Image preprocessing completed. No segmentation or clinical analysis was performed."


def save_attempt(
    db: Session,
    image: MedicalImage,
    current_user: User,
    *,
    result_metadata: dict[str, object] | None,
    failure_message: str | None,
) -> ImagePreprocessing:
    record = db.get(ImagePreprocessing, image.id)
    if record is None:
        record = ImagePreprocessing(image_id=image.id, preprocessed_by_id=current_user.id, status="failed", attempt_count=0)
        db.add(record)
    record.preprocessed_by_id = current_user.id
    record.attempt_count += 1
    record.status = "completed" if result_metadata is not None else "failed"
    record.result_metadata = result_metadata
    record.failure_message = failure_message
    db.commit()
    db.refresh(record)
    return record


def as_read(image_id: UUID, record: ImagePreprocessing | None) -> PreprocessingRead:
    if record is None:
        return PreprocessingRead(
            image_id=image_id,
            status="not_started",
            message="Preprocessing has not been run for this image.",
            attempt_count=0,
        )
    if record.status == "completed" and record.result_metadata is not None:
        return PreprocessingRead(
            image_id=image_id,
            status="completed",
            message=COMPLETED_MESSAGE,
            attempt_count=record.attempt_count,
            updated_at=record.updated_at,
            result=PreprocessingMetadata.model_validate(record.result_metadata),
        )
    return PreprocessingRead(
        image_id=image_id,
        status="failed",
        message=record.failure_message or "Preprocessing failed. You can retry.",
        attempt_count=record.attempt_count,
        updated_at=record.updated_at,
    )


@router.post("/images/{image_id}/preprocess", response_model=PreprocessingRead)
def preprocess_stored_image(
    image_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PreprocessingRead:
    query = select(MedicalImage).join(Case, Case.id == MedicalImage.case_id).where(MedicalImage.id == image_id)
    if current_user.role != "admin":
        query = query.where(Case.owner_id == current_user.id)
    image = db.scalar(query)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    settings = get_settings()
    try:
        path = resolve_storage_path(settings.upload_directory, image.storage_key)
    except ValueError as exc:
        save_attempt(db, image, current_user, result_metadata=None, failure_message="Image storage reference is invalid. Retry after the stored image is restored.")
        raise HTTPException(status_code=404, detail="Image file not found") from exc
    if not path.is_file():
        save_attempt(db, image, current_user, result_metadata=None, failure_message="Stored image file is unavailable. Retry after the stored image is restored.")
        raise HTTPException(status_code=404, detail="Image file not found")
    try:
        file_size = path.stat().st_size
    except OSError as exc:
        save_attempt(db, image, current_user, result_metadata=None, failure_message="Stored image file is unreadable. Retry after the stored image is restored.")
        raise HTTPException(status_code=404, detail="Image file not found") from exc
    if file_size > settings.max_upload_size_bytes:
        save_attempt(db, image, current_user, result_metadata=None, failure_message="Image exceeds the configured upload size limit. Retry after the file is corrected.")
        raise HTTPException(status_code=413, detail="Image exceeds the configured upload size limit")
    try:
        result = preprocess_image_file(
            path,
            image.original_filename,
            max_upload_size_bytes=settings.max_upload_size_bytes,
            max_image_pixels=settings.max_image_pixels,
        )
    except HTTPException:
        raise
    except PreprocessingError as exc:
        save_attempt(db, image, current_user, result_metadata=None, failure_message=f"{exc}. You can retry after correcting the image.")
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    record = save_attempt(db, image, current_user, result_metadata=result.metadata, failure_message=None)
    return as_read(image.id, record)


@router.get("/cases/{case_id}/preprocessing", response_model=list[PreprocessingRead])
def list_case_preprocessing(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PreprocessingRead]:
    case_query = select(Case).where(Case.id == case_id)
    if current_user.role != "admin":
        case_query = case_query.where(Case.owner_id == current_user.id)
    if db.scalar(case_query) is None:
        raise HTTPException(status_code=404, detail="Case not found")

    query = (
        select(MedicalImage, ImagePreprocessing)
        .outerjoin(ImagePreprocessing, ImagePreprocessing.image_id == MedicalImage.id)
        .where(MedicalImage.case_id == case_id)
        .order_by(MedicalImage.created_at.desc())
    )
    return [as_read(image.id, record) for image, record in db.execute(query).all()]
