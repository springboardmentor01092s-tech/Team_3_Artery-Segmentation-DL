from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, owned_or_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.models.case import Case
from app.models.image import MedicalImage
from app.models.user import User
from app.schemas.image import ImageRead
from app.services.storage import InvalidImage, clean_original_filename, resolve_storage_path, store_image

router = APIRouter(tags=["images"])


def accessible_case(case_id: UUID, db: Session, current_user: User) -> Case:
    case = db.scalar(owned_or_admin(select(Case), Case, current_user).where(Case.id == case_id))
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/cases/{case_id}/images", response_model=ImageRead, status_code=status.HTTP_201_CREATED)
async def upload_image(
    case_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MedicalImage:
    case = accessible_case(case_id, db, current_user)
    settings = get_settings()
    content = await file.read(settings.max_upload_size_bytes + 1)
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(status_code=413, detail="Image exceeds the configured upload size limit")
    original_filename = clean_original_filename(file.filename)
    try:
        storage_key, media_type, size_bytes, digest = store_image(
            content, original_filename, settings.upload_directory, settings.max_image_pixels
        )
    except InvalidImage as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    image = MedicalImage(
        case_id=case.id,
        uploaded_by_id=current_user.id,
        storage_key=storage_key,
        original_filename=original_filename,
        media_type=media_type,
        size_bytes=size_bytes,
        sha256=digest,
    )
    db.add(image)
    try:
        db.commit()
    except Exception:
        db.rollback()
        resolve_storage_path(settings.upload_directory, storage_key).unlink(missing_ok=True)
        raise
    db.refresh(image)
    return image


@router.get("/cases/{case_id}/images", response_model=list[ImageRead])
def list_case_images(
    case_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[MedicalImage]:
    accessible_case(case_id, db, current_user)
    query = select(MedicalImage).where(MedicalImage.case_id == case_id).order_by(MedicalImage.created_at.desc())
    return list(db.scalars(query).all())


@router.get("/images/{image_id}/content")
def get_image_content(
    image_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    query = select(MedicalImage).join(Case, Case.id == MedicalImage.case_id).where(MedicalImage.id == image_id)
    if current_user.role != "admin":
        query = query.where(Case.owner_id == current_user.id)
    image = db.scalar(query)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")
    try:
        path: Path = resolve_storage_path(get_settings().upload_directory, image.storage_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Image file not found") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Image file not found")
    return FileResponse(path, media_type=image.media_type, filename=image.original_filename)
