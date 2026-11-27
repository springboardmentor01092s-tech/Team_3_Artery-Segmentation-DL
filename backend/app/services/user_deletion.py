"""Owner-scoped user deletion and durable, retryable managed-file cleanup."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.analysis_run import AnalysisRun
from app.models.case import Case
from app.models.image import MedicalImage
from app.models.image_preprocessing import ImagePreprocessing
from app.models.notification import Notification
from app.models.patient import Patient
from app.models.user import User
from app.services.storage import resolve_storage_path


QUEUE_DIRECTORY = ".user-deletion-cleanups"
WIDTH_REASON = "resource_still_referenced"


class UserDeletionNotFound(Exception):
    pass


class UserDeletionRejected(Exception):
    """Deletion is not permitted for the account or ownership graph."""


class UserDeletionTransactionError(Exception):
    pass


def _root_directory(path: Path) -> Path:
    root = path.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _queue_directory(output_directory: Path) -> Path:
    root = _root_directory(output_directory)
    queue = root / QUEUE_DIRECTORY
    if queue.is_symlink():
        raise ValueError("Deletion cleanup storage is not a safe managed directory")
    queue.mkdir(exist_ok=True)
    resolved = queue.resolve()
    if resolved.parent != root or resolved.name != QUEUE_DIRECTORY:
        raise ValueError("Deletion cleanup storage is not a safe managed directory")
    return resolved


def _manifest_path(output_directory: Path, cleanup_id: uuid.UUID) -> Path:
    queue = _queue_directory(output_directory)
    return queue / f"{cleanup_id.hex}.json"


def _write_manifest(output_directory: Path, manifest: dict[str, Any]) -> Path:
    cleanup_id = uuid.UUID(manifest["cleanup_id"])
    target = _manifest_path(output_directory, cleanup_id)
    if target.is_symlink():
        raise ValueError("Deletion cleanup journal is not a regular managed file")
    # Keep the temporary leaf short for Windows MAX_PATH environments while
    # retaining per-writer uniqueness for concurrent journal updates.
    temporary = target.with_name(f".{cleanup_id.hex}.{uuid.uuid4().hex[:8]}.tmp")
    content = json.dumps(manifest, allow_nan=False, separators=(",", ":"))
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    return target


def _read_manifest(output_directory: Path, cleanup_id: uuid.UUID) -> tuple[Path, dict[str, Any]]:
    path = _manifest_path(output_directory, cleanup_id)
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError("Deletion cleanup record not found")
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or value.get("cleanup_id") != str(cleanup_id)
        or not isinstance(value.get("user_id"), str)
        or not isinstance(value.get("storage_keys"), list)
        or not all(isinstance(key, str) for key in value["storage_keys"])
        or not isinstance(value.get("analysis_run_ids"), list)
        or not all(isinstance(run_id, str) for run_id in value["analysis_run_ids"])
    ):
        raise ValueError("Deletion cleanup record is invalid")
    uuid.UUID(value["user_id"])
    for run_id in value["analysis_run_ids"]:
        parsed = uuid.UUID(run_id)
        if run_id != str(parsed):
            raise ValueError("Deletion cleanup record is invalid")
    return path, value


def _remove_manifest(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Deletion cleanup journal is not a regular managed file")
    path.unlink()


def _safe_upload_path(upload_directory: Path, storage_key: str) -> Path:
    original = upload_directory.resolve() / storage_key
    if original.is_symlink():
        raise ValueError("Uploaded file is a symbolic link")
    resolved = resolve_storage_path(upload_directory, storage_key)
    if resolved.name != storage_key or (resolved.exists() and not resolved.is_file()):
        raise ValueError("Uploaded file is not a regular managed file")
    return resolved


def _safe_run_directory(output_directory: Path, run_id: uuid.UUID) -> Path:
    root = output_directory.resolve()
    candidate = root / run_id.hex
    if candidate.is_symlink():
        raise ValueError("Analysis artifact directory is a symbolic link")
    resolved = candidate.resolve()
    if resolved.parent != root or resolved.name != run_id.hex:
        raise ValueError("Analysis artifact directory is outside managed storage")
    if resolved.exists() and not resolved.is_dir():
        raise ValueError("Analysis artifact path is not a directory")
    return resolved


def _delete_upload_file(path: Path) -> None:
    if path.exists():
        path.unlink()


def _delete_analysis_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _remember_cleanup_error(output_directory: Path, manifest: dict[str, Any], code: str) -> None:
    manifest["last_error"] = code
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_manifest(output_directory, manifest)


def _best_effort_remember_cleanup_error(output_directory: Path, manifest: dict[str, Any], code: str) -> None:
    try:
        _remember_cleanup_error(output_directory, manifest, code)
    except Exception:
        # The original durable manifest remains the retry source if updating
        # its diagnostic status is not possible.
        pass


def retry_user_deletion_cleanup(db: Session, cleanup_id: uuid.UUID, settings: Settings) -> dict[str, Any]:
    """Idempotently remove only unreferenced files from a validated cleanup journal."""
    path, manifest = _read_manifest(settings.analysis_output_directory, cleanup_id)
    user_id = uuid.UUID(manifest["user_id"])
    if db.get(User, user_id) is not None:
        # A failed/ambiguous DB transaction left the account intact. Never remove
        # storage while the owner row still exists.
        try:
            _remove_manifest(path)
        except Exception:
            _best_effort_remember_cleanup_error(settings.analysis_output_directory, manifest, "journal_cleanup_failed")
            return {"cleanup_id": cleanup_id, "status": "pending", "detail": "The deletion transaction did not complete; cleanup journal removal is pending."}
        return {"cleanup_id": cleanup_id, "status": "not_deleted", "detail": "The account remains; no files were removed."}

    upload_paths: list[Path] = []
    run_paths: list[Path] = []
    try:
        for storage_key in manifest["storage_keys"]:
            if db.scalar(select(MedicalImage.id).where(MedicalImage.storage_key == storage_key)) is not None:
                _best_effort_remember_cleanup_error(settings.analysis_output_directory, manifest, WIDTH_REASON)
                return {"cleanup_id": cleanup_id, "status": "pending", "detail": "A stored image is still referenced; cleanup was safely deferred."}
            upload_paths.append(_safe_upload_path(settings.upload_directory, storage_key))
        for raw_run_id in manifest["analysis_run_ids"]:
            run_id = uuid.UUID(raw_run_id)
            if db.get(AnalysisRun, run_id) is not None:
                _best_effort_remember_cleanup_error(settings.analysis_output_directory, manifest, WIDTH_REASON)
                return {"cleanup_id": cleanup_id, "status": "pending", "detail": "An analysis run is still referenced; cleanup was safely deferred."}
            run_paths.append(_safe_run_directory(settings.analysis_output_directory, run_id))
        for file_path in upload_paths:
            _delete_upload_file(file_path)
        for run_path in run_paths:
            _delete_analysis_directory(run_path)
        _remove_manifest(path)
    except (OSError, ValueError, json.JSONDecodeError):
        _best_effort_remember_cleanup_error(settings.analysis_output_directory, manifest, "file_cleanup_failed_or_path_rejected")
        return {"cleanup_id": cleanup_id, "status": "pending", "detail": "Some managed files could not be safely removed; retry is available."}
    return {"cleanup_id": cleanup_id, "status": "complete", "detail": "All unreferenced managed files were removed."}


def list_pending_user_deletion_cleanups(output_directory: Path) -> list[dict[str, Any]]:
    # Listing status must not create storage directories as a side effect.
    root = output_directory.resolve()
    queue = root / QUEUE_DIRECTORY
    if not queue.exists() and not queue.is_symlink():
        return []
    if queue.is_symlink() or not queue.is_dir() or queue.resolve().parent != root:
        raise ValueError("Deletion cleanup storage is not a safe managed directory")
    pending: list[dict[str, Any]] = []
    for path in sorted(queue.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            cleanup_id = uuid.UUID(hex=path.stem)
            _, manifest = _read_manifest(output_directory, cleanup_id)
        except (ValueError, OSError, json.JSONDecodeError):
            continue
        pending.append({
            "cleanup_id": cleanup_id,
            "created_at": manifest.get("created_at"),
            "storage_file_count": len(manifest["storage_keys"]),
            "analysis_run_count": len(manifest["analysis_run_ids"]),
            "last_error": manifest.get("last_error"),
        })
    return pending


def delete_regular_user(db: Session, user_id: uuid.UUID, administrator_id: uuid.UUID, settings: Settings) -> dict[str, Any]:
    """Delete a Regular User's data and every record dependent on that data."""
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise UserDeletionNotFound
    if user.id == administrator_id:
        raise UserDeletionRejected("An administrator cannot delete their own account.")
    if user.role != "user":
        raise UserDeletionRejected("Only Regular User accounts can be permanently deleted.")

    patients = list(db.scalars(select(Patient).where(Patient.owner_id == user_id).with_for_update()).all())
    patient_ids = {row.id for row in patients}
    case_query = select(Case)
    case_terms = [Case.owner_id == user_id]
    if patient_ids:
        case_terms.append(Case.patient_id.in_(patient_ids))
    case_query = case_query.where(or_(*case_terms))
    cases = list(db.scalars(case_query.with_for_update()).all())
    case_ids = {row.id for row in cases}

    # A case is dependent on its patient; an image is dependent on its case.
    # The creator/requester fields do not transfer ownership of the underlying
    # source record, so cross-owner dependent rows must be removed as well.
    image_terms = [MedicalImage.uploaded_by_id == user_id]
    if case_ids:
        image_terms.append(MedicalImage.case_id.in_(case_ids))
    images = list(db.scalars(select(MedicalImage).where(or_(*image_terms)).with_for_update()).all())
    image_ids = {row.id for row in images}

    run_terms = [AnalysisRun.requested_by_id == user_id]
    if case_ids:
        run_terms.append(AnalysisRun.case_id.in_(case_ids))
    if image_ids:
        run_terms.append(AnalysisRun.image_id.in_(image_ids))
    runs = list(db.scalars(select(AnalysisRun).where(or_(*run_terms)).with_for_update()).all())

    preprocessing_terms = [ImagePreprocessing.preprocessed_by_id == user_id]
    if image_ids:
        preprocessing_terms.append(ImagePreprocessing.image_id.in_(image_ids))
    preprocessing_rows = list(
        db.scalars(select(ImagePreprocessing).where(or_(*preprocessing_terms)).with_for_update()).all()
    )

    # Resolve every path before writing the journal or changing database state.
    for image in images:
        _safe_upload_path(settings.upload_directory, image.storage_key)
    for run in runs:
        _safe_run_directory(settings.analysis_output_directory, run.id)

    cleanup_id = uuid.uuid4()
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "cleanup_id": str(cleanup_id),
        "user_id": str(user_id),
        "storage_keys": [image.storage_key for image in images],
        "analysis_run_ids": [str(run.id) for run in runs],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_error": None,
    }
    journal_path = _write_manifest(settings.analysis_output_directory, manifest)

    try:
        for row in [*preprocessing_rows, *runs, *images, *cases, *patients]:
            db.delete(row)
        notifications = list(db.scalars(select(Notification).where(Notification.user_id == user_id).with_for_update()).all())
        for row in notifications:
            db.delete(row)
        db.delete(user)
        db.commit()
    except Exception as exc:
        db.rollback()
        try:
            still_exists = db.get(User, user_id) is not None
        except Exception:
            still_exists = False
            try:
                _remember_cleanup_error(settings.analysis_output_directory, manifest, "database_outcome_unknown")
            except OSError:
                pass
            raise UserDeletionTransactionError(cleanup_id) from exc
        if still_exists:
            try:
                _remove_manifest(journal_path)
            except OSError:
                try:
                    _remember_cleanup_error(settings.analysis_output_directory, manifest, "database_delete_rolled_back")
                except OSError:
                    pass
            raise UserDeletionTransactionError(None) from exc

    try:
        cleanup = retry_user_deletion_cleanup(db, cleanup_id, settings)
    except Exception:
        # The database transaction is already committed. Keep the durable
        # journal so a later admin retry can safely finish physical cleanup.
        _best_effort_remember_cleanup_error(settings.analysis_output_directory, manifest, "file_cleanup_retry_required")
        cleanup = {
            "status": "pending",
            "detail": "The account was deleted, but managed-file cleanup could not be confirmed; retry is available.",
        }
    return {
        "deleted_user_id": user_id,
        "cleanup_status": "complete" if cleanup["status"] == "complete" else "pending",
        "cleanup_id": None if cleanup["status"] == "complete" else cleanup_id,
        "detail": cleanup["detail"],
    }
