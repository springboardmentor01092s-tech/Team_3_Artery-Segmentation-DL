"""Validation and safe resolution for private analysis artifacts."""

from __future__ import annotations

import json
import io
import shutil
import uuid
from pathlib import Path, PurePosixPath

from PIL import Image, UnidentifiedImageError


ARTIFACT_MEDIA_TYPES = {
    "artery_mask.png": "image/png",
    "stenosis_mask.png": "image/png",
    "candidate_overlay.png": "image/png",
    "combined_visualization.png": "image/png",
    "gradcam.png": "image/png",
    "candidates.json": "application/json",
}
REQUIRED_ARTIFACTS = set(ARTIFACT_MEDIA_TYPES) - {"gradcam.png"}


def create_analysis_run_directory(output_directory: Path, run_id: uuid.UUID) -> Path:
    root = output_directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_directory = (root / run_id.hex).resolve()
    if run_directory.parent != root:
        raise ValueError("Invalid analysis artifact directory")
    run_directory.mkdir(exist_ok=False)
    return run_directory


def validate_artifact_manifest(
    output_directory: Path,
    run_id: uuid.UUID,
    manifest: object,
    *,
    expected_image_size: tuple[int, int],
) -> dict[str, str]:
    """Validate exact artifact names, run containment, content type and dimensions."""
    if not isinstance(manifest, dict) or set(manifest) not in (REQUIRED_ARTIFACTS, set(ARTIFACT_MEDIA_TYPES)):
        raise ValueError("Analysis artifact manifest is incomplete")

    safe_keys: dict[str, str] = {}
    image_width, image_height = expected_image_size
    for filename in manifest:
        relative_key = manifest.get(filename)
        if not isinstance(relative_key, str):
            raise ValueError("Invalid analysis artifact reference")
        path = resolve_analysis_artifact_path(output_directory, run_id, relative_key)
        if filename.endswith(".png"):
            try:
                with Image.open(path) as image:
                    if image.format != "PNG":
                        raise ValueError("Analysis artifact is not a PNG")
                    width, height = image.size
                    image.verify()
            except (OSError, UnidentifiedImageError) as exc:
                raise ValueError("Analysis artifact is unreadable") from exc
            if filename in {"artery_mask.png", "stenosis_mask.png", "candidate_overlay.png"}:
                if (width, height) != (image_width, image_height):
                    raise ValueError("Analysis artifact dimensions do not match the source image")
            elif filename == "gradcam.png":
                if (width, height) != (512, 512):
                    raise ValueError("Grad-CAM dimensions must be 512x512")
            elif not (1 <= width <= 4096 and 1 <= height <= 4096):
                raise ValueError("Combined visualization dimensions are invalid")
        else:
            if path.stat().st_size > 5 * 1024 * 1024:
                raise ValueError("Candidate metadata artifact exceeds its size limit")
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("Candidate metadata artifact is unreadable") from exc
            if not isinstance(document, dict) or not isinstance(document.get("candidates"), list):
                raise ValueError("Candidate metadata artifact has an invalid structure")
        safe_keys[filename] = relative_key
    return safe_keys


def resolve_analysis_artifact_path(output_directory: Path, run_id: uuid.UUID, relative_key: str) -> Path:
    """Resolve a persisted relative key without permitting traversal or arbitrary reads."""
    if not isinstance(relative_key, str) or "\\" in relative_key:
        raise ValueError("Invalid analysis artifact key")
    parts = PurePosixPath(relative_key).parts
    if len(parts) != 2 or parts[0] != run_id.hex or parts[1] not in ARTIFACT_MEDIA_TYPES:
        raise ValueError("Invalid analysis artifact key")

    root = output_directory.resolve()
    run_directory = (root / run_id.hex).resolve()
    target = (run_directory / parts[1]).resolve()
    if run_directory.parent != root or target.parent != run_directory:
        raise ValueError("Invalid analysis artifact path")
    if not target.is_file():
        raise FileNotFoundError("Analysis artifact not found")
    return target


def cleanup_analysis_run_directory(output_directory: Path, run_id: uuid.UUID) -> None:
    """Remove only this run's generated directory after a failed, incomplete run."""
    root = output_directory.resolve()
    run_directory = (root / run_id.hex).resolve()
    if run_directory.parent == root and run_directory.name == run_id.hex and run_directory.is_dir():
        shutil.rmtree(run_directory)


def render_legacy_combined_visualization(path: Path) -> bytes | None:
    """Repair the two {0,1} grayscale mask panels in old montages in memory only."""
    try:
        with Image.open(path) as opened:
            if opened.format != "PNG":
                return None
            image = opened.convert("RGB")
    except (OSError, UnidentifiedImageError):
        return None

    width, height = image.size
    panel_width = width // 2
    panel_height = height // 2 - 30
    if panel_width < 1 or panel_height < 1 or width != panel_width * 2 or height != (panel_height + 30) * 2:
        return None

    artery_box = (panel_width, 30, width, 30 + panel_height)
    # The second row starts after one full panel (image plus title), and its
    # image content starts after that row's own 30px title band.
    stenosis_box = (0, panel_height + 60, panel_width, height)
    artery_mask = image.crop(artery_box).convert("L")
    stenosis_mask = image.crop(stenosis_box).convert("L")
    if max(artery_mask.getextrema()[1], stenosis_mask.getextrema()[1]) > 1:
        return None

    image.paste(artery_mask.point(lambda value: value * 255).convert("RGB"), artery_box)
    image.paste(stenosis_mask.point(lambda value: value * 255).convert("RGB"), stenosis_box)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
