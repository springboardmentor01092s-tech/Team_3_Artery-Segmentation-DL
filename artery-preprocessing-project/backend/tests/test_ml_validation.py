import numpy as np
import json
from PIL import Image

from app.arcade_ml import audit_validation
from app.arcade_ml import evaluate_syntax_vessels
from app.arcade_ml.audit_validation import _metric_from_counts
from app.arcade_ml.coco import STENOSIS_CATEGORY_ID, filter_annotations, rasterize_polygons
from app.arcade_ml.dataset import ArcadeSegDataset
from app.arcade_ml.losses import BinaryFocalLoss, FocalTverskyLoss
from app.arcade_ml.normalization import normalize_rgb_array
import torch


def test_coco_mask_uses_category_26_and_exact_image_dimensions():
    annotations = [
        {"category_id": 26, "segmentation": [[1, 1, 6, 1, 6, 6, 1, 6]]},
        {"category_id": 2, "segmentation": [[10, 10, 14, 10, 14, 14, 10, 14]]},
    ]
    chosen = filter_annotations(annotations, STENOSIS_CATEGORY_ID)
    mask = rasterize_polygons(32, 24, chosen)
    assert mask.size == (32, 24)
    assert np.asarray(mask).sum() > 0
    assert np.asarray(mask)[12, 12] == 0


def test_empty_mask_metrics_use_documented_smoothed_convention():
    empty = _metric_from_counts(0, 0, 0, 512 * 512)
    assert empty["dice"] == 1.0
    assert empty["iou"] == 1.0
    false_positive = _metric_from_counts(0, 20, 0, 100)
    assert false_positive["dice"] == 1e-7 / 20.0000001
    assert false_positive["specificity"] < 1.0


def test_imagenet_normalization_is_finite_and_shared_for_rgb_preprocessing():
    rgb = np.asarray([[[0.0, 0.5, 1.0]]], dtype=np.float32)
    normalized = normalize_rgb_array(rgb, "imagenet")
    assert normalized.shape == rgb.shape
    assert np.isfinite(normalized).all()
    assert np.allclose(normalized[0, 0], (-0.485 / 0.229, (0.5 - 0.456) / 0.224, (1 - 0.406) / 0.225))
    assert np.array_equal(normalize_rgb_array(rgb, "none"), rgb)


def test_routine_dataset_audit_does_not_open_test_split(monkeypatch):
    calls = []

    def fake_audit(task, split):
        calls.append((task, split))
        return {"task": task, "split": split, "hashes": {},
                "categories": [{"name": "stenosis"}] if task == "stenosis" and split == "train" else []}

    monkeypatch.setattr(audit_validation, "audit_split", fake_audit)
    result = audit_validation.audit_dataset()
    assert result["test_split_included"] is False
    assert all(split != "test" for _, split in calls)
    assert len(calls) == 4


def test_focal_losses_return_finite_scalar():
    logits = torch.tensor([[[[-2.0, 2.0], [0.5, -0.5]]]], requires_grad=True)
    targets = torch.tensor([[[[0.0, 1.0], [1.0, 0.0]]]])
    for loss_fn in (BinaryFocalLoss(), FocalTverskyLoss()):
        loss = loss_fn(logits, targets)
        assert loss.ndim == 0
        assert torch.isfinite(loss)


def test_syntax_dataset_union_uses_all_annotated_vessel_segment_polygons(monkeypatch, tmp_path):
    split = tmp_path / "syntax_val"
    (split / "images").mkdir(parents=True)
    (split / "annotations").mkdir()
    Image.fromarray(np.zeros((32, 32), dtype=np.uint8)).save(split / "images" / "case.png")
    coco = {
        "images": [{"id": 1, "file_name": "case.png", "width": 32, "height": 32}],
        "categories": [{"id": 1, "name": "1"}, {"id": 2, "name": "2"}],
        "annotations": [
            {"id": 1, "image_id": 1, "category_id": 1, "segmentation": [[2, 2, 10, 2, 10, 8, 2, 8]]},
            {"id": 2, "image_id": 1, "category_id": 2, "segmentation": [[18, 18, 28, 18, 28, 28, 18, 28]]},
        ],
    }
    (split / "annotations" / "val.json").write_text(json.dumps(coco), encoding="utf-8")
    monkeypatch.setattr("app.arcade_ml.dataset.syntax_split_dir", lambda _split: split)
    dataset = ArcadeSegDataset("syntax", "val", image_size=32)
    _image, mask, filename = dataset[0]
    assert filename == "case.png"
    assert mask[0, 4, 4] == 1 and mask[0, 22, 22] == 1
    assert mask[0, 15, 15] == 0


def test_syntax_vessel_evaluator_uses_validation_union_only(monkeypatch, tmp_path):
    dataset = tmp_path / "arcade"
    val = dataset / "syntax" / "val"
    (val / "images").mkdir(parents=True)
    (val / "annotations").mkdir()
    Image.fromarray(np.zeros((12, 12), dtype=np.uint8)).save(val / "images" / "vessel.png")
    coco = {
        "images": [{"id": 5, "file_name": "vessel.png", "width": 12, "height": 12}],
        "categories": [{"id": 1, "name": "1"}],
        "annotations": [{"id": 1, "image_id": 5, "category_id": 1,
                         "segmentation": [[3, 3, 8, 3, 8, 8, 3, 8]]}],
    }
    (val / "annotations" / "val.json").write_text(json.dumps(coco), encoding="utf-8")
    monkeypatch.setattr(evaluate_syntax_vessels, "arcade_root", lambda: dataset)
    class FakeModel:
        def eval(self):
            return self

    monkeypatch.setattr(evaluate_syntax_vessels, "load_checkpoint", lambda *_: (FakeModel(), {
        "task": "syntax", "resolved_architecture": "unet", "image_size": 12, "normalization": "none",
    }))
    probs = np.zeros((12, 12), dtype=np.float32)
    probs[3:9, 3:9] = 0.9
    monkeypatch.setattr(evaluate_syntax_vessels, "predict_image", lambda *_args, **_kwargs: probs)
    report = evaluate_syntax_vessels.evaluate_syntax_vessel_checkpoint(
        tmp_path / "syntax_experiment.pth", tmp_path / "reports", thresholds=(0.5,)
    )
    assert report["dataset_split"] == "syntax/val"
    assert report["samples_evaluated"] == 1
    assert report["test_split_used"] is False
    assert report["global_pixel_metrics"]["dice"] == 1.0
    assert "not a clinically validated lumen-caliber estimator" in report["limitations"][0]
    assert report["visual_examples"]
    assert (tmp_path / "reports" / "syntax_experiment_syntax_validation_examples" / "worst_dice_vessel.png").is_file()
