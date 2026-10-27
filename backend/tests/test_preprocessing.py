import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.services.preprocessing import PreprocessingConfig, PreprocessingError, preprocess_image_file


def save_image(path: Path, mode: str, color) -> bytes:
    stream = io.BytesIO()
    Image.new(mode, (8, 4), color=color).save(stream, format="PNG")
    content = stream.getvalue()
    path.write_bytes(content)
    return content


def preprocess(path: Path, filename: str):
    return preprocess_image_file(
        path,
        filename,
        max_upload_size_bytes=1024 * 1024,
        max_image_pixels=1000,
        config=PreprocessingConfig((16, 16)),
    )


def test_preprocessing_returns_normalized_shape_dtype_and_preserves_original(tmp_path):
    path = tmp_path / "source.png"
    original = save_image(path, "RGB", (128, 64, 32))

    result = preprocess(path, "source.png")

    assert result.pixels.shape == (1, 16, 16)
    assert result.pixels.dtype == np.float32
    assert np.isfinite(result.pixels).all()
    assert float(result.pixels.min()) >= 0
    assert float(result.pixels.max()) <= 1
    assert result.metadata["model_batch_shape"] == [1, 1, 16, 16]
    assert result.metadata["channel_format"] == "CHW, one grayscale channel"
    assert path.read_bytes() == original


def test_preprocessing_preserves_unsigned_16_bit_intensity_range(tmp_path):
    path = tmp_path / "source.png"
    save_image(path, "I;16", 32768)

    result = preprocess(path, "source.png")

    assert result.pixels.dtype == np.float32
    assert np.isclose(result.pixels.max(), 32768 / 65535, atol=0.01)


@pytest.mark.parametrize(
    ("content", "filename", "pixel_limit"),
    [
        (b"not an image", "source.png", 1000),
        (b"not an image", "source.gif", 1000),
        (None, "source.png", 4),
    ],
)
def test_preprocessing_rejects_corrupt_unsupported_and_over_limit_images(tmp_path, content, filename, pixel_limit):
    path = tmp_path / "source.png"
    if content is None:
        save_image(path, "L", 80)
    else:
        path.write_bytes(content)

    with pytest.raises(PreprocessingError):
        preprocess_image_file(
            path,
            filename,
            max_upload_size_bytes=1024 * 1024,
            max_image_pixels=pixel_limit,
            config=PreprocessingConfig((16, 16)),
        )


def test_preprocessing_rejects_stored_file_over_size_limit(tmp_path):
    path = tmp_path / "source.png"
    save_image(path, "L", 80)

    with pytest.raises(PreprocessingError, match="size limit"):
        preprocess_image_file(
            path,
            "source.png",
            max_upload_size_bytes=1,
            max_image_pixels=1000,
            config=PreprocessingConfig((16, 16)),
        )
