# XYZ Trainer — Line Drawing → 3D Coordinate Map

A PyTorch pipeline that trains a U-Net to translate monochrome line drawings
into RGB-encoded XYZ coordinate maps, where each pixel's color encodes its
3D world-space position (R=X, G=Y, B=Z).

---

## File Overview

| File | Purpose |
|------|---------|
| `dataset.py` | Dataset class, augmentation pipelines, dataloader builder |
| `model.py` | U-Net with attention gates |
| `losses.py` | Combined L1 + gradient + surface normal + SSIM loss |
| `metrics.py` | MAE, RMSE, AbsRel, δ accuracy, surface normal error |
| `train.py` | Main training loop with checkpointing and early stopping |
| `infer.py` | Inference on single images or directories |

---

## Data Directory Layout

Your dataset must follow this structure:

```
data/
├── line_drawings/
│   ├── 00001.png
│   ├── 00002.png
│   └── ...
└── xyz_maps/
    ├── 00001.png   ← same filenames as line drawings
    ├── 00002.png
    └── ...
```

**XYZ map encoding:** Each channel of the XYZ map image stores one world-space
axis, normalized to `[0, 255]`:
- R channel → X coordinate
- G channel → Y coordinate
- B channel → Z (depth) coordinate

Keep a record of the min/max values you used for normalization — you'll need
them to decode model outputs back to real-world units during inference.

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Training

```bash
# Basic run with defaults (256×256, batch 16, 200 epochs)
python train.py --data_root ./data

# Custom settings
python train.py \
    --data_root     ./data \
    --image_size    256 \
    --batch_size    16 \
    --epochs        200 \
    --lr            2e-4 \
    --base_features 64 \
    --depth         4 \
    --dropout       0.2 \
    --w_l1          1.0 \
    --w_grad        0.5 \
    --w_normal      0.3 \
    --w_ssim        0.2

# Resume from checkpoint
python train.py --data_root ./data --resume checkpoints/last.pt

# Enable Weights & Biases logging
python train.py --data_root ./data --wandb --wandb_project my-xyz-project
```

Checkpoints are saved to `./checkpoints/`:
- `best.pt` — best validation loss model
- `last.pt` — most recent epoch (for resuming)
- `epoch_050.pt`, `epoch_100.pt`, ... — periodic saves

Prediction visualizations (input | prediction | ground truth) are saved to
`./checkpoints/vis/` every 10 epochs by default.

---

## Inference

```bash
# Single image
python infer.py \
    --checkpoint checkpoints/best.pt \
    --input      drawing.png \
    --output     results/

# Directory of images
python infer.py \
    --checkpoint checkpoints/best.pt \
    --input      ./drawings/ \
    --output     ./results/

# Decode output to real-world XYZ coordinates (saves .npy alongside .png)
python infer.py \
    --checkpoint checkpoints/best.pt \
    --input      drawing.png \
    --xyz_min    -1.0 -1.0  0.0 \
    --xyz_max     1.0  1.0  2.0
```

Output files per image:
- `{name}_xyz.png` — RGB-encoded XYZ map (viewable image)
- `{name}_xyz.npy` — decoded float32 array in real-world units (if `--xyz_min/max` provided)

---

## Key Design Decisions

### Why U-Net?
Encoder-decoder with skip connections preserves fine spatial detail, which is
critical for accurate per-pixel coordinate regression. The attention gates
additionally suppress irrelevant skip features.

### Why not pure MSE loss?
MSE heavily penalizes large errors and produces blurry predictions. The
combined L1 + gradient + normal loss produces sharper, geometrically consistent
outputs.

### Data augmentation strategy
- **Joint transforms** (applied identically to input and target): flips,
  rotations, shifts, crops — preserves spatial correspondence.
- **Input-only transforms**: noise, blur, brightness, elastic deformation —
  simulates drawing style variation without corrupting XYZ targets.

---

## Tuning Tips

| Problem | Try |
|---------|-----|
| Blurry predictions | Increase `--w_grad` and `--w_normal` |
| Overfitting | Increase `--dropout`, reduce `--base_features` |
| Slow convergence | Increase `--lr` to `5e-4`, check data normalization |
| Wrong Z scale | Verify your XYZ normalization min/max values |
| Out of memory | Reduce `--batch_size` or `--image_size` |
