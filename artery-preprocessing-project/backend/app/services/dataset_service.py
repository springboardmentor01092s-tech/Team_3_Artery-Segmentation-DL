import json
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.arcade_ml.paths import arcade_root
from app.models.image import UploadedImage
from app.models.user import User
from app.preprocessing.exceptions import ImageValidationError, UnsupportedImageError
from app.preprocessing.pipeline import load_image, validate_image
from app.repositories import cases as case_repo
from app.services.image_service import original_path
from app.utils.files import SUPPORTED_EXTENSIONS


def _inspect_file(path: Path, max_bytes: int) -> tuple[str | None, bool]:
    if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return None, False
    try:
        validate_image(path, max_bytes)
        loaded = load_image(path)
        return loaded.format, False
    except (ImageValidationError, UnsupportedImageError):
        return None, True


def _inspect_paths(paths: list[Path], max_bytes: int) -> tuple[int, int, dict[str, int]]:
    formats: Counter[str] = Counter()
    supported = 0
    unreadable = 0
    for path in paths:
        fmt, failed = _inspect_file(path, max_bytes)
        if failed:
            unreadable += 1
        elif fmt is not None:
            formats[fmt] += 1
            supported += 1
    return supported, unreadable, dict(formats)


def _sample_image_paths(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _accessible_uploaded_paths(db: Session, user: User) -> list[Path]:
    visible_ids = case_repo.visible_case_ids(db, user)
    images = list(db.scalars(select(UploadedImage).where(UploadedImage.case_id.in_(visible_ids))).all())
    return [original_path(image) for image in images]


def _arcade_split_summary(root: Path, task: str, split: str) -> dict:
    split_dir = root / task / split
    image_dir = split_dir / "images"
    image_count = sum(
        1 for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ) if image_dir.is_dir() else 0
    summary = {
        "directory": str(split_dir),
        "exists": split_dir.is_dir(),
        "image_count": image_count,
        "annotation_status": "not_inspected" if split == "test" else "missing",
        "annotation_image_count": None,
        "annotation_count": None,
        "category_ids": [],
        "selection_eligible": split in {"train", "val"},
        "note": "Test split is a holdout; its annotation file is not opened or used by this summary."
        if split == "test" else "Training and validation annotations are reported separately.",
    }
    # Never open test COCO files: this endpoint is an inventory, not test evaluation.
    if split == "test":
        return summary

    annotation_path = split_dir / "annotations" / f"{split}.json"
    if not annotation_path.is_file():
        return summary
    try:
        with annotation_path.open(encoding="utf-8") as handle:
            coco = json.load(handle)
        images = coco.get("images")
        annotations = coco.get("annotations")
        if not isinstance(images, list) or not isinstance(annotations, list):
            raise ValueError("COCO images and annotations must be lists")
        if task == "stenosis":
            relevant = [ann for ann in annotations if int(ann.get("category_id", -1)) == 26]
        else:
            relevant = [ann for ann in annotations if 1 <= int(ann.get("category_id", -1)) <= 25]
        category_ids = sorted({int(ann["category_id"]) for ann in relevant})
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        summary.update({"annotation_status": "invalid", "note": "COCO annotation file exists but could not be summarized."})
        return summary

    summary.update({
        "annotation_status": "available",
        "annotation_image_count": len(images),
        "annotation_count": len(relevant),
        "category_ids": category_ids,
        "annotation_file": str(annotation_path),
        "note": "Counts are annotation inventory only; no model selection or evaluation was run.",
    })
    return summary


def _arcade_summary() -> dict:
    root = arcade_root()
    return {
        "root": str(root),
        "exists": root.is_dir(),
        "tasks": {
            task: {split: _arcade_split_summary(root, task, split) for split in ("train", "val", "test")}
            for task in ("stenosis", "syntax")
        },
    }


def summarize_dataset(db: Session, user: User, directory: Path | None = None) -> dict:
    settings = get_settings()
    sample_root = directory or settings.resolved_dataset_dir()
    upload_root = settings.resolved_upload_dir()
    max_bytes = settings.max_upload_bytes

    sample_exists = sample_root.exists()
    sample_supported, sample_unreadable, sample_formats = _inspect_paths(
        _sample_image_paths(sample_root),
        max_bytes,
    )
    uploaded_supported, uploaded_unreadable, uploaded_formats = _inspect_paths(
        _accessible_uploaded_paths(db, user),
        max_bytes,
    )

    if not sample_exists:
        sample_note = (
            "No sample dataset directory was found. Place de-identified public images in "
            "data/sample_images or set DATASET_DIR."
        )
    elif sample_supported == 0 and sample_unreadable == 0:
        sample_note = "No sample images found"
    else:
        sample_note = "Sample counts include only supported files that currently exist in the sample directory."

    uploaded_note = (
        "Uploaded case images are counted only when the file exists, is a supported format, "
        "and belongs to a case you can access."
    )

    combined_formats: Counter[str] = Counter(sample_formats)
    combined_formats.update(uploaded_formats)
    supported = sample_supported + uploaded_supported
    unreadable = sample_unreadable + uploaded_unreadable

    if not sample_exists or (sample_supported == 0 and sample_unreadable == 0):
        overall_note = (
            f"{sample_note}. Uploaded case images are listed separately and are not missing from the sample dataset."
        )
    else:
        overall_note = "Summary reflects files currently present. Statistics are not invented for missing datasets."

    sample = {
        "directory": str(sample_root),
        "exists": sample_exists,
        "supported_count": sample_supported,
        "unreadable_count": sample_unreadable,
        "formats": sample_formats,
        "note": sample_note,
    }
    uploaded = {
        "directory": str(upload_root),
        "exists": upload_root.exists(),
        "supported_count": uploaded_supported,
        "unreadable_count": uploaded_unreadable,
        "formats": uploaded_formats,
        "note": uploaded_note,
    }
    return {
        "directory": str(sample_root),
        "exists": sample_exists,
        "supported_count": supported,
        "unreadable_count": unreadable,
        "formats": dict(combined_formats),
        "note": overall_note,
        "sample_supported_count": sample_supported,
        "uploaded_supported_count": uploaded_supported,
        "sample": sample,
        "uploaded": uploaded,
        "arcade": _arcade_summary(),
    }
