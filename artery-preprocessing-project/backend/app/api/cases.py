
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_permission
from app.core.permissions import Permission
from app.models.preprocessing import PreprocessingRun
from app.models.user import User
from app.schemas.case import AccessCandidateOut, CaseAccessGrant, CaseAccessOut, CaseCreate, CaseOut, CaseUpdate, ImageSummary
from app.schemas.preprocessing import PreprocessRequest, PreprocessingRunOut
from app.services import case_service, image_service

router = APIRouter(prefix="/api/cases", tags=["cases"])


def check_case_access(db: Session, user: User, case_id: str):
    """
    Return a case only if the user is allowed to access it.

    Administrators can access all cases.
    Other users can access their own cases and cases explicitly
    assigned or shared with them.

    The actual visibility rules are enforced by case_service.
    """
    return case_service.get_accessible_case(db, user, case_id)


@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: CaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.CASE_CREATE)),
):
    case = case_service.create_case(db, user, payload)
    return case_service.to_out(case, user)


@router.get("", response_model=list[CaseOut])
def list_cases(
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.CASE_READ_OWN)),
):
    """
    List only cases visible to the current user.

    case_service.list_cases must filter by ownership, explicit assignment,
    and sharing. Administrators should receive all cases.
    """
    cases = case_service.list_cases(db, user, search)
    return [case_service.to_out(case, user) for case in cases]


@router.get("/{case_id}", response_model=CaseOut)
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = check_case_access(db, user, case_id)
    include_grants = case_service.can_manage_case_access(user, case)
    return case_service.to_out(case, user, include_grants=include_grants)


@router.patch("/{case_id}", response_model=CaseOut)
def update_case(
    case_id: str,
    payload: CaseUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.CASE_UPDATE_OWN)),
):
    case = check_case_access(db, user, case_id)
    case = case_service.update_case(db, user, case, payload)
    return case_service.to_out(case, user)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.CASE_DELETE_OWN)),
):
    case = check_case_access(db, user, case_id)
    image_service.remove_case_files(case)
    case_service.delete_case(db, user, case)


@router.post("/{case_id}/upload", response_model=ImageSummary)
def upload(
    case_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.IMAGE_UPLOAD)),
):
    case = check_case_access(db, user, case_id)
    return image_service.upload_image(db, user, case, file)


@router.get("/{case_id}/image")
def get_image(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = check_case_access(db, user, case_id)

    if not case.images:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No image has been uploaded for this case.",
        )

    image = sorted(
        case.images,
        key=lambda item: item.uploaded_at,
        reverse=True,
    )[0]

    path = image_service.original_path(image)

    return FileResponse(
        path,
        filename=image.original_filename,
        media_type="application/octet-stream",
    )


@router.post(
    "/{case_id}/preprocess",
    response_model=PreprocessingRunOut,
)
def preprocess(
    case_id: str,
    payload: PreprocessRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.IMAGE_PREPROCESS)),
):
    case = check_case_access(db, user, case_id)
    return image_service.run_preprocessing(db, user, case, payload)


@router.get(
    "/{case_id}/preprocessing-history",
    response_model=list[PreprocessingRunOut],
)
def history(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = check_case_access(db, user, case_id)

    stmt = (
        select(PreprocessingRun)
        .where(PreprocessingRun.case_id == case.id)
        .order_by(PreprocessingRun.started_at.desc())
    )

    return list(db.scalars(stmt).all())


@router.get("/{case_id}/processed-image/{run_id}")
def get_processed(
    case_id: str,
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = check_case_access(db, user, case_id)

    run = db.get(PreprocessingRun, run_id)

    if run is None or run.case_id != case.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preprocessing run not found.",
        )

    path = image_service.processed_path(run)

    return FileResponse(
        path,
        filename="preprocessed.png",
        media_type="image/png",
    )


@router.get("/{case_id}/access", response_model=list[CaseAccessOut])
def list_case_access(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = check_case_access(db, user, case_id)
    grants = case_service.list_access(db, user, case)
    return [case_service.grant_to_out(grant) for grant in grants]


@router.get("/{case_id}/access-candidates", response_model=list[AccessCandidateOut])
def list_access_candidates(
    case_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = check_case_access(db, user, case_id)
    return case_service.list_access_candidates(db, user, case)


@router.post("/{case_id}/access", response_model=CaseAccessOut, status_code=status.HTTP_201_CREATED)
def grant_case_access(
    case_id: str,
    payload: CaseAccessGrant,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = check_case_access(db, user, case_id)
    grant = case_service.grant_access(db, user, case, payload.user_id, payload.access_type)
    return case_service.grant_to_out(grant)


@router.delete("/{case_id}/access/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_case_access(
    case_id: str,
    grant_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = check_case_access(db, user, case_id)
    case_service.revoke_access(db, user, case, grant_id)
