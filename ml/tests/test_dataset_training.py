import sys

import numpy as np
import pytest
import torch
from PIL import Image
from torch.utils.data import DataLoader, TensorDataset

from ml.dataset import ArcadeSyntaxDataset
from ml.train_baseline import combined_segmentation_loss, parse_args, run_epoch, select_subset


def make_syntax_layout(tmp_path, *, include_mask=True):
    dataset_root = tmp_path / "source"
    mask_root = tmp_path / "prepared"
    image_dir = dataset_root / "syntax" / "train" / "images"
    mask_dir = mask_root / "syntax" / "train" / "masks"
    image_dir.mkdir(parents=True)
    mask_dir.mkdir(parents=True)
    Image.fromarray(np.full((12, 20), 127, dtype=np.uint8), mode="L").save(image_dir / "sample-1.png")
    if include_mask:
        Image.fromarray(np.array([[0, 2], [7, 0]], dtype=np.uint8), mode="L").save(mask_dir / "sample-1.png")
    return dataset_root, mask_root


def test_pairs_by_filename_and_returns_binary_256_square_tensors(tmp_path):
    dataset_root, mask_root = make_syntax_layout(tmp_path)
    dataset = ArcadeSyntaxDataset(dataset_root, mask_root, "train")

    image, mask = dataset[0]

    assert len(dataset) == 1
    assert image.shape == (1, 256, 256)
    assert image.dtype == torch.float32
    assert torch.isclose(image.mean(), torch.tensor(127 / 255), atol=1e-4)
    assert mask.shape == (1, 256, 256)
    assert mask.dtype == torch.float32
    assert set(torch.unique(mask).tolist()) == {0.0, 1.0}
    # Category IDs 2 and 7 are both foreground; zero stays background after nearest resize.
    assert mask[0, 10, 200] == 1
    assert mask[0, 200, 10] == 1
    assert mask[0, 10, 10] == 0
    assert mask[0, 200, 200] == 0


def test_raises_clear_error_for_unmatched_image(tmp_path):
    dataset_root, mask_root = make_syntax_layout(tmp_path, include_mask=False)

    with pytest.raises(ValueError, match="no matching prepared mask.*sample-1.png"):
        ArcadeSyntaxDataset(dataset_root, mask_root, "train")


def test_dataset_accepts_configured_resolution_and_sample_limit(tmp_path):
    dataset_root, mask_root = make_syntax_layout(tmp_path)
    dataset = ArcadeSyntaxDataset(dataset_root, mask_root, "train", image_size=(64, 64))
    selected = select_subset(dataset, 1)

    image, mask = selected[0]

    assert len(selected) == 1
    assert image.shape == mask.shape == (1, 64, 64)


def test_cli_parses_cpu_resolution_and_smoke_sample_options(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "train_baseline",
            "--image-size", "128",
            "--batch-size", "1",
            "--cpu-threads", "2",
            "--limit-train-samples", "4",
            "--limit-val-samples", "2",
        ],
    )

    args = parse_args()

    assert args.image_size == 128
    assert args.batch_size == 1
    assert args.cpu_threads == 2
    assert args.limit_train_samples == 4
    assert args.limit_val_samples == 2


def test_run_epoch_reports_epoch_and_batch_progress(capsys):
    model = torch.nn.Conv2d(1, 1, kernel_size=1)
    images = torch.ones((1, 1, 16, 16))
    masks = torch.zeros_like(images)
    loader = DataLoader(TensorDataset(images, masks), batch_size=1)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

    run_epoch(
        model,
        loader,
        torch.device("cpu"),
        epoch=2,
        total_epochs=5,
        phase="train",
        log_every=10,
        optimizer=optimizer,
    )

    output = capsys.readouterr().out
    assert "Epoch 2/5 | train batch 1/1 starting" in output
    assert "Epoch 2/5 | train batch 1/1 complete" in output


def test_combined_bce_dice_loss_matches_expected_value_and_backpropagates():
    logits = torch.zeros((1, 1, 2, 2), requires_grad=True)
    targets = torch.zeros_like(logits)

    loss = combined_segmentation_loss(logits, targets)

    expected = 0.5 * (np.log(2.0) + (1.0 - 1.0 / 3.0))
    assert loss.item() == pytest.approx(expected, rel=1e-6)
    loss.backward()
    assert logits.grad is not None
    assert torch.isfinite(logits.grad).all()
