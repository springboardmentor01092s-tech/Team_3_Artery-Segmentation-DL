"""Dataset reader for the prepared ARCADE syntax split images and masks."""

from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset


IMAGE_SIZE = (256, 256)
_MASK_MODES = {"1", "L", "P", "I", "I;16", "I;16B", "I;16L"}


class ArcadeSyntaxDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    """Load one syntax split without modifying its source PNGs.

    Expected layout:
      dataset_root/syntax/<split>/images/*.png
      mask_root/syntax/<split>/masks/*.png
    Pairing uses the filename stem.
    """

    def __init__(
        self,
        dataset_root: str | Path,
        mask_root: str | Path,
        split: str,
        image_size: tuple[int, int] = IMAGE_SIZE,
    ) -> None:
        if split not in {"train", "val", "test"}:
            raise ValueError("split must be one of: train, val, test")
        if len(image_size) != 2 or any(dimension <= 0 for dimension in image_size):
            raise ValueError("image_size must contain positive width and height")
        if any(dimension % 16 != 0 for dimension in image_size):
            raise ValueError("image dimensions must be divisible by 16 for the existing U-Net")

        self.image_size = image_size
        image_directory = Path(dataset_root) / "syntax" / split / "images"
        mask_directory = Path(mask_root) / "syntax" / split / "masks"
        if not image_directory.is_dir():
            raise FileNotFoundError(f"Image directory for syntax/{split} was not found: {image_directory}")
        if not mask_directory.is_dir():
            raise FileNotFoundError(f"Prepared mask directory for syntax/{split} was not found: {mask_directory}")

        images = sorted(image_directory.glob("*.png"), key=lambda path: (path.stem.casefold(), path.name.casefold()))
        masks_by_stem = {path.stem.casefold(): path for path in mask_directory.glob("*.png")}
        missing_masks = [path.name for path in images if path.stem.casefold() not in masks_by_stem]
        if missing_masks:
            sample = ", ".join(missing_masks[:5])
            suffix = "…" if len(missing_masks) > 5 else ""
            raise ValueError(f"{len(missing_masks)} syntax/{split} image(s) have no matching prepared mask: {sample}{suffix}")

        image_stems = {path.stem.casefold() for path in images}
        orphan_masks = sorted(path.name for stem, path in masks_by_stem.items() if stem not in image_stems)
        if orphan_masks:
            sample = ", ".join(orphan_masks[:5])
            suffix = "…" if len(orphan_masks) > 5 else ""
            raise ValueError(f"{len(orphan_masks)} prepared syntax/{split} mask(s) have no matching image: {sample}{suffix}")
        if not images:
            raise ValueError(f"No PNG images found in syntax/{split}: {image_directory}")

        self.samples = [(image_path, masks_by_stem[image_path.stem.casefold()]) for image_path in images]

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        image_path, mask_path = self.samples[index]
        with Image.open(image_path) as source_image:
            image = source_image.convert("L").resize(self.image_size, Image.Resampling.LANCZOS)
            image_array = np.asarray(image, dtype=np.float32) / 255.0

        with Image.open(mask_path) as source_mask:
            if source_mask.mode not in _MASK_MODES:
                raise ValueError(f"Prepared mask must contain category IDs in a single channel: {mask_path} (mode={source_mask.mode})")
            mask = source_mask.resize(self.image_size, Image.Resampling.NEAREST)
            mask_array = np.asarray(mask)
        if mask_array.ndim != 2:
            raise ValueError(f"Prepared mask must be a single-channel category-ID image: {mask_path}")
        binary_mask = (mask_array != 0).astype(np.float32)

        image_tensor = torch.from_numpy(np.ascontiguousarray(image_array[None, :, :]))
        mask_tensor = torch.from_numpy(np.ascontiguousarray(binary_mask[None, :, :]))
        return image_tensor, mask_tensor
