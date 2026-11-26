from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

from .coco import STENOSIS_CATEGORY_ID, filter_annotations, index_coco, load_coco, rasterize_polygons
from .normalization import normalize_rgb_array
from .paths import stenosis_split_dir, syntax_split_dir


class ArcadeSegDataset(Dataset):
    """Reads original ARCADE images (read-only) and rasterizes masks in memory."""

    def __init__(
        self,
        task: str,
        split: str,
        image_size: int = 256,
        augment: bool = False,
        augmentation_mode: str = "conservative",
        normalization: str = "none",
        category_id: int | None = None,
        max_samples: int | None = None,
    ):
        if split not in {"train", "val", "test"}:
            raise ValueError(split)
        if task not in {"stenosis", "syntax"}:
            raise ValueError(task)
        self.task = task
        self.split = split
        self.image_size = image_size
        self.augment = augment and split == "train"
        if augmentation_mode not in {"conservative", "legacy"}:
            raise ValueError(f"Unknown augmentation mode: {augmentation_mode}")
        self.augmentation_mode = augmentation_mode
        if normalization not in {"none", "imagenet"}:
            raise ValueError(f"Unknown normalization mode: {normalization}")
        self.normalization = normalization
        root = stenosis_split_dir(split) if task == "stenosis" else syntax_split_dir(split)
        self.image_dir = root / "images"
        json_path = root / "annotations" / f"{split}.json"
        coco = load_coco(json_path)
        indexed = index_coco(coco)
        self.category_id = STENOSIS_CATEGORY_ID if task == "stenosis" else category_id
        self.records = list(indexed.values())
        self.records.sort(key=lambda item: item["file_name"])
        self.excluded_duplicates: list[str] = []
        self.excluded_within_split_duplicates: list[str] = []
        if split == "train":
            held_out_hashes: set[str] = set()
            # Validation hashes prevent train/validation leakage. The test split
            # is deliberately not read by training or experiment selection.
            for held_out_split in ("val",):
                held_out_root = stenosis_split_dir(held_out_split) if task == "stenosis" else syntax_split_dir(held_out_split)
                annotation_path = held_out_root / "annotations" / f"{held_out_split}.json"
                if not annotation_path.is_file():
                    continue
                held_out_coco = load_coco(annotation_path)
                for item in held_out_coco.get("images", []):
                    held_out_path = held_out_root / "images" / item["file_name"]
                    if held_out_path.is_file():
                        held_out_hashes.add(hashlib.sha256(held_out_path.read_bytes()).hexdigest())
            kept = []
            seen_train_hashes: set[str] = set()
            for item in self.records:
                train_path = self.image_dir / item["file_name"]
                digest = hashlib.sha256(train_path.read_bytes()).hexdigest()
                if digest in held_out_hashes:
                    self.excluded_duplicates.append(item["file_name"])
                elif digest in seen_train_hashes:
                    self.excluded_within_split_duplicates.append(item["file_name"])
                else:
                    kept.append(item)
                    seen_train_hashes.add(digest)
            self.records = kept
        if max_samples is not None:
            self.records = self.records[: max(1, int(max_samples))]

    def __len__(self) -> int:
        return len(self.records)

    def _augment(self, image: Image.Image, mask: Image.Image) -> tuple[Image.Image, Image.Image]:
        if self.augmentation_mode == "conservative":
            from PIL import ImageEnhance

            angle = float(np.random.uniform(-10.0, 10.0))
            image = image.rotate(angle, resample=Image.Resampling.BILINEAR, fillcolor=(0, 0, 0))
            mask = mask.rotate(angle, resample=Image.Resampling.NEAREST, fillcolor=0)
            image = ImageEnhance.Brightness(image).enhance(float(np.random.uniform(0.9, 1.1)))
            image = ImageEnhance.Contrast(image).enhance(float(np.random.uniform(0.9, 1.1)))
            return image, mask
        if np.random.rand() < 0.5:
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
            mask = mask.transpose(Image.FLIP_LEFT_RIGHT)
        if np.random.rand() < 0.5:
            image = image.transpose(Image.FLIP_TOP_BOTTOM)
            mask = mask.transpose(Image.FLIP_TOP_BOTTOM)
        k = int(np.random.choice([0, 1, 2, 3]))
        if k:
            image = image.rotate(90 * k, expand=False)
            mask = mask.rotate(90 * k, expand=False)
        return image, mask

    def __getitem__(self, index: int):
        rec = self.records[index]
        image_path = self.image_dir / rec["file_name"]
        image = Image.open(image_path).convert("RGB")
        anns = filter_annotations(rec["annotations"], self.category_id)
        if self.task == "syntax":
            anns = rec["annotations"]
        mask = rasterize_polygons(image.width, image.height, anns)
        image = image.resize((self.image_size, self.image_size), Image.Resampling.BILINEAR)
        mask = mask.resize((self.image_size, self.image_size), Image.Resampling.NEAREST)
        if self.augment:
            image, mask = self._augment(image, mask)
        image_arr = np.asarray(image, dtype=np.float32) / 255.0
        image_arr = normalize_rgb_array(image_arr, self.normalization)
        mask_arr = (np.asarray(mask, dtype=np.uint8) > 0).astype(np.float32)
        image_t = torch.from_numpy(image_arr).permute(2, 0, 1)
        mask_t = torch.from_numpy(mask_arr).unsqueeze(0)
        return image_t, mask_t, rec["file_name"]
