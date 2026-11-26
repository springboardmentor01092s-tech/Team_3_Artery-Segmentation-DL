from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image
import pydicom
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

from app.preprocessing.pipeline import (
    _dicom_pixel_spacing_metadata,
    load_image,
    normalize_intensity,
    preprocess_image,
    reduce_noise,
    resize_image,
    validate_image,
)


def test_dicom_pixel_spacing_metadata_validates_and_preserves_order():
    metadata = _dicom_pixel_spacing_metadata(SimpleNamespace(
        PixelSpacing=["0.31", "0.27"], PixelSpacingCalibrationType="GEOMETRY"
    ))
    assert metadata["pixel_spacing"] == [0.31, 0.27]
    assert metadata["pixel_spacing_status"] == "reported_valid_values"
    assert metadata["pixel_spacing_order"] == "row_column"
    assert metadata["pixel_spacing_unit"] == "mm_per_pixel"
    assert metadata["pixel_spacing_calibration_type"] == "GEOMETRY"


def test_dicom_pixel_spacing_metadata_rejects_invalid_and_missing_values():
    for raw in (["0.3"], ["0", "0.4"], ["nan", "0.4"], ["inf", "0.4"], ["bad", "0.4"]):
        metadata = _dicom_pixel_spacing_metadata(SimpleNamespace(PixelSpacing=raw))
        assert metadata["pixel_spacing"] is None
        assert metadata["pixel_spacing_status"] == "invalid_values"
    missing = _dicom_pixel_spacing_metadata(SimpleNamespace())
    assert missing["pixel_spacing"] is None
    assert missing["pixel_spacing_status"] == "unavailable"


def test_load_dicom_retains_reported_pixel_spacing(tmp_path: Path):
    path = tmp_path / "calibrated-metadata.dcm"
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()
    ds = FileDataset(str(path), {}, file_meta=file_meta, preamble=b"\0" * 128)
    ds.SOPClassUID = SecondaryCaptureImageStorage
    ds.SOPInstanceUID = file_meta.MediaStorageSOPInstanceUID
    ds.Modality = "XA"
    ds.Rows = 16
    ds.Columns = 16
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelSpacing = ["0.31", "0.27"]
    ds.PixelSpacingCalibrationType = "GEOMETRY"
    ds.PixelData = bytes(range(256))
    ds.save_as(path)

    loaded = load_image(path)
    assert loaded.is_dicom is True
    assert loaded.metadata["pixel_spacing"] == [0.31, 0.27]
    assert loaded.metadata["pixel_spacing_status"] == "reported_valid_values"
    assert loaded.metadata["pixel_spacing_calibration_type"] == "GEOMETRY"


def test_pipeline_preserves_source(tmp_path: Path):
    source = tmp_path / "src.png"
    dest = tmp_path / "out.png"
    Image.new("L", (80, 60), color=40).save(source)
    original = source.read_bytes()
    result = preprocess_image(
        source,
        dest,
        max_bytes=5_000_000,
        params={
            "normalize": True,
            "normalize_method": "minmax",
            "resize": True,
            "target_width": 40,
            "target_height": 40,
            "preserve_aspect_ratio": True,
            "denoise": False,
            "contrast": False,
        },
    )
    assert source.read_bytes() == original
    assert dest.exists()
    assert result["original_width"] == 80
    assert result["processed_width"] <= 40


def test_validate_rejects_empty(tmp_path: Path):
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    try:
        validate_image(empty, 1000)
        assert False, "expected failure"
    except Exception as exc:
        assert "empty" in str(exc).lower()


def test_normalize_and_filters():
    arr = np.linspace(10, 200, 64, dtype=np.float32).reshape(8, 8)
    normed = normalize_intensity(arr, "minmax")
    assert float(normed.min()) == 0.0
    resized = resize_image(arr, 16, 16, preserve_aspect_ratio=True)
    assert resized.shape[0] == 16
    denoised = reduce_noise(arr, "median", 3)
    assert denoised.shape[0] == 8
