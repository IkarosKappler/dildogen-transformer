"""
dataset.py - Dataset and augmentation pipeline for line drawing → XYZ map training.

Expects a data directory with the structure:
    data/
        line_drawings/   # grayscale .png/.jpg files
        xyz_maps/        # RGB-encoded XYZ coordinate .png files (same filenames)

XYZ maps must be pre-normalized to [0, 255] before saving, where each channel
encodes one world-space axis. Keep track of your normalization min/max values
so you can decode predictions back to real-world coordinates.
"""

import os
import numpy as np
from pathlib import Path
from PIL import Image

import torch
from torch.utils.data import Dataset, DataLoader, random_split
import albumentations as A
from albumentations.pytorch import ToTensorV2
import re 


# ---------------------------------------------------------------------------
# Augmentation pipelines
# ---------------------------------------------------------------------------

def get_joint_transform(image_size: int, is_train: bool) -> A.Compose:
    """
    Geometric transforms applied IDENTICALLY to both the line drawing and
    the XYZ map. Spatial correspondence must be preserved.
    """
    if is_train:
        transforms = [
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.2),
            A.RandomRotate90(p=0.4),
            A.ShiftScaleRotate(
                shift_limit=0.1,
                scale_limit=0.2,
                rotate_limit=30,
                border_mode=0,       # constant padding (black)
                p=0.6,
            ),
            A.RandomCrop(height=image_size, width=image_size, p=0.5),
            A.Resize(height=image_size, width=image_size),
        ]
    else:
        transforms = [
            A.Resize(height=image_size, width=image_size),
        ]

    return A.Compose(
        transforms,
        additional_targets={"xyz_map": "image"},  # apply same ops to xyz_map
    )


def get_input_transform(is_train: bool) -> A.Compose:
    """
    Appearance transforms applied to the LINE DRAWING ONLY.
    These simulate variation in drawing style without corrupting XYZ targets.
    """
    if is_train:
        return A.Compose([
            A.GaussNoise(var_limit=(5.0, 25.0), p=0.3),
            A.RandomBrightnessContrast(
                brightness_limit=0.2, contrast_limit=0.2, p=0.4
            ),
            A.Blur(blur_limit=3, p=0.2),
            A.ElasticTransform(
                alpha=30, sigma=5, p=0.2
            ),  # simulates hand-drawn stroke variation
            A.Sharpen(alpha=(0.1, 0.3), p=0.2),
        ])
    else:
        return A.Compose([])  # no augmentation at eval time

def get_datafile_base_name(filename:str) -> str:
    # print("filename", filename)
    # Drop last number here: this is random
    # m = re.search(r'[0-9]+-[0-9]+-[0-9]+', filename)
    m = re.search(r'[0-9]+-[0-9]+', filename)
    # print("group?", filename, m.group)
    if m: 
        # print("group is", m.group(0))
        return m.group(0)
    # else: return undefined value??

# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class XYZDataset(Dataset):
    """
    Paired dataset of (line_drawing, xyz_map) images.

    Args:
        line_dir:    Path to folder of grayscale line drawing images.
        xyz_dir:     Path to folder of RGB XYZ map images (same filenames).
        image_size:  Square crop/resize target (e.g. 256).
        is_train:    Whether to apply training augmentations.
        extensions:  Accepted file extensions.
    """

    def __init__(
        self,
        sample_data_dir: str,
        # xyz_dir: str,
        image_size: int = 256,
        is_train: bool = True,
        # extensions: tuple = (".png", ".jpg", ".jpeg"),
        extensions: tuple = (".png"),
    ):
        # self.line_dir = Path(line_dir)
        # self.xyz_dir = Path(xyz_dir)
        self.sample_data_dir = Path(sample_data_dir)
        self.image_size = image_size
        self.is_train = is_train

        # Collect file stems that exist in BOTH directories
        # line_stems = {
        #     p.stem for p in self.line_dir.iterdir()
        #     if p.suffix.lower() in extensions
        # }
        # xyz_stems = {
        #     p.stem for p in self.xyz_dir.iterdir()
        #     if p.suffix.lower() in extensions
        # }
        # common = sorted(line_stems & xyz_stems)

        # uploads/2026/03/20260311-224028-55668-preview2d_b64.png
        # uploads/2026/03/20260311-224028-55668-sculptmap_b64.png
        line_stems = {
            p.stem for p in self.sample_data_dir.iterdir()
            # .match(r'[0-9]+.*\.jpg', f)]
            if p.suffix.lower() in extensions and re.match(r'[0-9]+-[0-9]+-[0-9]+-preview2d.*\.png',p.name)
        }
        xyz_stems = {
            p.stem for p in self.sample_data_dir.iterdir()
            if p.suffix.lower() in extensions and re.match(r'[0-9]+-[0-9]+-[0-9]+-sculptmap.*\.png',p.name)
        }
        #print(line_stems)
        # print(xyz_stems)
        line_stems_base = set(map(get_datafile_base_name, line_stems))
        xyz_stems_base = set({map(get_datafile_base_name, xyz_stems)})
        # print("line_stems_base",line_stems_base)
        print("xyz_stems_base",xyz_stems_base) # 20260312-010412-32556

        common = sorted(line_stems_base & xyz_stems_base)
        print("common", common)

        if not common:
            raise ValueError(
                f"No matching file pairs found in "
                f"'{sample_data_dir}'."
            )

        # Resolve full paths (pick the first matching extension)
        self.samples = []
        for stem in common:
            line_path = self._find_file(self.line_dir, stem, extensions)
            xyz_path  = self._find_file(self.xyz_dir,  stem, extensions)
            if line_path and xyz_path:
                self.samples.append((line_path, xyz_path))

        self.joint_transform  = get_joint_transform(image_size, is_train)
        self.input_transform  = get_input_transform(is_train)

        # Final conversion to normalized float tensors
        self.to_tensor = ToTensorV2()

        print(
            f"[Dataset] {'Train' if is_train else 'Val/Test'} — "
            f"{len(self.samples)} pairs | size={image_size}"
        )

    # ------------------------------------------------------------------
    def _find_file(self, directory: Path, stem: str, extensions: tuple):
        for ext in extensions:
            p = directory / (stem + ext)
            if p.exists():
                return p
        return None

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        line_path, xyz_path = self.samples[idx]

        # Load images
        line_img = np.array(Image.open(line_path).convert("L"))   # H×W, uint8
        xyz_img  = np.array(Image.open(xyz_path).convert("RGB"))  # H×W×3, uint8

        # --- Joint geometric augmentation ---
        result   = self.joint_transform(image=line_img, xyz_map=xyz_img)
        line_img = result["image"]    # H×W
        xyz_img  = result["xyz_map"]  # H×W×3

        # --- Input-only appearance augmentation ---
        line_img = self.input_transform(image=line_img)["image"]   # H×W

        # --- Normalize to [0, 1] float32 ---
        line_tensor = torch.from_numpy(line_img).float().unsqueeze(0) / 255.0  # 1×H×W
        xyz_tensor  = torch.from_numpy(xyz_img).float().permute(2, 0, 1) / 255.0  # 3×H×W

        return line_tensor, xyz_tensor


# ---------------------------------------------------------------------------
# Convenience: build train / val / test loaders from a single root directory
# ---------------------------------------------------------------------------

def build_dataloaders(
    data_root: str,
    image_size: int = 256,
    batch_size: int = 16,
    num_workers: int = 4,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    seed: int = 42,
):
    """
    Splits data into train/val/test and returns three DataLoaders.

    Expected directory layout:
        data_root/
            line_drawings/
            xyz_maps/
    """
    print("Loading dataset")
    line_dir = os.path.join(data_root, "line_drawings")
    xyz_dir  = os.path.join(data_root, "xyz_maps")

    # Build a full dataset (no augmentation) just to get all file pairs
    full_dataset = XYZDataset(line_dir, xyz_dir, image_size, is_train=False)
    n = len(full_dataset)

    n_train = int(n * train_ratio)
    n_val   = int(n * val_ratio)
    n_test  = n - n_train - n_val

    generator = torch.Generator().manual_seed(seed)
    train_indices, val_indices, test_indices = random_split(
        range(n), [n_train, n_val, n_test], generator=generator
    )

    # Now build properly augmented datasets using the same file list
    def make_subset(indices, is_train):
        ds = XYZDataset(line_dir, xyz_dir, image_size, is_train=is_train)
        return torch.utils.data.Subset(ds, list(indices))

    train_ds = make_subset(train_indices, is_train=True)
    val_ds   = make_subset(val_indices,   is_train=False)
    test_ds  = make_subset(test_indices,  is_train=False)

    loader_kwargs = dict(
        batch_size=batch_size,
        num_workers=num_workers,
        pin_memory=True,
    )

    train_loader = DataLoader(train_ds, shuffle=True,  **loader_kwargs)
    val_loader   = DataLoader(val_ds,   shuffle=False, **loader_kwargs)
    test_loader  = DataLoader(test_ds,  shuffle=False, **loader_kwargs)

    print(
        f"[Dataloaders] Train={len(train_ds)} | "
        f"Val={len(val_ds)} | Test={len(test_ds)}"
    )
    return train_loader, val_loader, test_loader
