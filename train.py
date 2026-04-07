"""
train.py - Main training loop for line drawing → XYZ map model.

Features:
  - Mixed precision training (AMP) for speed on modern GPUs
  - Cosine LR schedule with warm-up
  - Early stopping
  - Checkpoint saving (best val loss + periodic)
  - Weights & Biases logging (optional, falls back to console)
  - Visualizes sample predictions each epoch

Usage:
    python train.py --data_root ./data --epochs 200 --batch_size 16
    python train.py --data_root ./data --resume checkpoints/last.pt
"""

import argparse
import os
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.cuda.amp import GradScaler, autocast
import numpy as np
from PIL import Image

from classes.dataset import build_dataloaders
from model   import UNet
from losses  import XYZLoss
from metrics import RunningMetrics

# Optional W&B logging — gracefully disabled if not installed
try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False


# ---------------------------------------------------------------------------
# Learning rate scheduler with linear warm-up + cosine decay
# ---------------------------------------------------------------------------

def build_scheduler(optimizer, warmup_epochs: int, total_epochs: int):
    """Linear warm-up for the first N epochs, cosine decay thereafter."""

    def lr_lambda(epoch):
        if epoch < warmup_epochs:
            return (epoch + 1) / warmup_epochs
        progress = (epoch - warmup_epochs) / max(1, total_epochs - warmup_epochs)
        return 0.5 * (1.0 + np.cos(np.pi * progress))

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def save_checkpoint(state: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    torch.save(state, path)


def load_checkpoint(path: str, model, optimizer=None, scheduler=None):
    ckpt = torch.load(path, map_location="cpu")
    model.load_state_dict(ckpt["model"])
    if optimizer  and "optimizer"  in ckpt: optimizer.load_state_dict(ckpt["optimizer"])
    if scheduler  and "scheduler"  in ckpt: scheduler.load_state_dict(ckpt["scheduler"])
    return ckpt.get("epoch", 0), ckpt.get("best_val_loss", float("inf"))


# ---------------------------------------------------------------------------
# Visualization helper
# ---------------------------------------------------------------------------

def save_prediction_grid(
    line_imgs:  torch.Tensor,
    pred_xyz:   torch.Tensor,
    target_xyz: torch.Tensor,
    save_path:  str,
    n:          int = 4,
):
    """
    Saves a side-by-side grid: [input | prediction | ground truth]
    for the first `n` samples in the batch.
    """
    n = min(n, line_imgs.shape[0])
    rows = []
    for i in range(n):
        inp  = (line_imgs[i, 0].cpu().numpy() * 255).astype(np.uint8)
        inp  = np.stack([inp] * 3, axis=-1)                               # H×W×3
        pred = (pred_xyz[i].permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)
        gt   = (target_xyz[i].permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)
        row  = np.concatenate([inp, pred, gt], axis=1)                    # H×(3W)×3
        rows.append(row)

    grid = np.concatenate(rows, axis=0)                                   # (nH)×(3W)×3
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    Image.fromarray(grid).save(save_path)


# ---------------------------------------------------------------------------
# One epoch
# ---------------------------------------------------------------------------

def run_epoch(
    model,
    loader,
    criterion,
    optimizer,
    scaler,
    device,
    is_train: bool,
    metrics_tracker: RunningMetrics,
):
    model.train() if is_train else model.eval()
    total_loss   = 0.0
    total_comps  = {}
    metrics_tracker.reset()

    ctx = torch.enable_grad() if is_train else torch.no_grad()

    with ctx:
        for line_imgs, xyz_targets in loader:
            line_imgs   = line_imgs.to(device,   non_blocking=True)
            xyz_targets = xyz_targets.to(device, non_blocking=True)

            # with autocast(enabled=(scaler is not None)):
            with torch.amp.autocast("cuda", enabled=(scaler is not None)):
                preds = model(line_imgs)
                loss, comps = criterion(preds, xyz_targets)

            if is_train:
                optimizer.zero_grad(set_to_none=True)
                if scaler is not None:
                    scaler.scale(loss).backward()
                    scaler.unscale_(optimizer)
                    nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    loss.backward()
                    nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                    optimizer.step()

            total_loss += comps["loss/total"]
            for k, v in comps.items():
                total_comps[k] = total_comps.get(k, 0.0) + v

            metrics_tracker.update(preds.detach().float(), xyz_targets.float())

    n_batches    = len(loader)
    avg_loss     = total_loss / n_batches
    avg_comps    = {k: v / n_batches for k, v in total_comps.items()}
    epoch_metrics = metrics_tracker.compute()

    return avg_loss, {**avg_comps, **epoch_metrics}, (line_imgs, preds, xyz_targets)


# ---------------------------------------------------------------------------
# Early stopping
# ---------------------------------------------------------------------------

class EarlyStopping:
    def __init__(self, patience: int = 20, min_delta: float = 1e-4):
        self.patience  = patience
        self.min_delta = min_delta
        self.counter   = 0
        self.best      = float("inf")

    def __call__(self, val_loss: float) -> bool:
        if val_loss < self.best - self.min_delta:
            self.best    = val_loss
            self.counter = 0
        else:
            self.counter += 1
        return self.counter >= self.patience


# ---------------------------------------------------------------------------
# Main training function
# ---------------------------------------------------------------------------

def train(args):
    device = torch.device(
        "cuda"  if torch.cuda.is_available()  else
        "mps"   if torch.backends.mps.is_available() else
        "cpu"
    )
    print(f"[Train] Device: {device}")

    # --- Data ---
    train_loader, val_loader, _ = build_dataloaders(
        data_root   = args.data_root,
        image_size  = args.image_size,
        batch_size  = args.batch_size,
        num_workers = args.num_workers,
    )

    # --- Model ---
    model = UNet(
        in_channels   = 1,
        out_channels  = 3,
        base_features = args.base_features,
        depth         = args.depth,
        dropout       = args.dropout,
        use_attention = True,
    ).to(device)
    print(f"[Model] Parameters: {model.count_parameters():,}")

    # --- Optimizer & scheduler ---
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )
    scheduler = build_scheduler(optimizer, warmup_epochs=10, total_epochs=args.epochs)
    scaler    = GradScaler() if device.type == "cuda" else None

    # --- Loss & metrics ---
    criterion = XYZLoss(
        w_l1=args.w_l1, w_grad=args.w_grad,
        w_normal=args.w_normal, w_ssim=args.w_ssim,
    )
    train_metrics = RunningMetrics()
    val_metrics   = RunningMetrics()

    # --- Resume ---
    start_epoch    = 0
    best_val_loss  = float("inf")
    ckpt_dir       = Path(args.checkpoint_dir)

    if args.resume:
        start_epoch, best_val_loss = load_checkpoint(
            args.resume, model, optimizer, scheduler
        )
        print(f"[Resume] Epoch {start_epoch} | best val loss: {best_val_loss:.4f}")

    # --- W&B ---
    use_wandb = WANDB_AVAILABLE and args.wandb
    if use_wandb:
        wandb.init(project=args.wandb_project, config=vars(args))
        wandb.watch(model, log_freq=100)

    early_stop = EarlyStopping(patience=args.patience)

    # -----------------------------------------------------------------------
    # Training loop
    # -----------------------------------------------------------------------
    for epoch in range(start_epoch, args.epochs):
        t0 = time.time()

        train_loss, train_logs, _ = run_epoch(
            model, train_loader, criterion, optimizer, scaler,
            device, is_train=True, metrics_tracker=train_metrics,
        )
        val_loss, val_logs, (imgs, preds, targets) = run_epoch(
            model, val_loader, criterion, optimizer=None, scaler=None,
            device=device, is_train=False, metrics_tracker=val_metrics,
        )

        scheduler.step()
        elapsed = time.time() - t0
        lr      = optimizer.param_groups[0]["lr"]

        # --- Console log ---
        print(
            f"Epoch [{epoch+1:03d}/{args.epochs}] "
            f"train={train_loss:.4f} val={val_loss:.4f} "
            f"lr={lr:.2e} time={elapsed:.1f}s"
        )
        print(
            f"  MAE={val_logs.get('metric/mae', 0):.4f} "
            f"RMSE={val_logs.get('metric/rmse', 0):.4f} "
            f"δ1.25={val_logs.get('metric/delta_1_25', 0):.3f} "
            f"NormErr={val_logs.get('metric/angle_err', 0):.2f}°"
        )

        # --- W&B log ---
        if use_wandb:
            log_dict = {
                "epoch": epoch + 1, "lr": lr,
                **{f"train/{k}": v for k, v in train_logs.items()},
                **{f"val/{k}":   v for k, v in val_logs.items()},
            }
            wandb.log(log_dict)

        # --- Save prediction visualization ---
        if (epoch + 1) % args.vis_every == 0:
            vis_path = str(ckpt_dir / f"vis/epoch_{epoch+1:03d}.png")
            save_prediction_grid(imgs, preds, targets, vis_path)
            if use_wandb:
                wandb.log({"val/predictions": wandb.Image(vis_path)})

        # --- Checkpoint: best model ---
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            save_checkpoint(
                {
                    "epoch": epoch + 1,
                    "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(),
                    "scheduler": scheduler.state_dict(),
                    "best_val_loss": best_val_loss,
                    "args": vars(args),
                },
                str(ckpt_dir / "best.pt"),
            )
            print(f"  ✓ New best model saved (val_loss={best_val_loss:.4f})")

        # --- Checkpoint: periodic ---
        if (epoch + 1) % args.save_every == 0:
            save_checkpoint(
                {"epoch": epoch + 1, "model": model.state_dict()},
                str(ckpt_dir / f"epoch_{epoch+1:03d}.pt"),
            )

        # --- Always save last ---
        save_checkpoint(
            {
                "epoch": epoch + 1,
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "scheduler": scheduler.state_dict(),
                "best_val_loss": best_val_loss,
            },
            str(ckpt_dir / "last.pt"),
        )

        # --- Early stopping ---
        if early_stop(val_loss):
            print(f"[Early Stop] No improvement for {args.patience} epochs. Stopping.")
            break

    print(f"\nTraining complete. Best val loss: {best_val_loss:.4f}")
    if use_wandb:
        wandb.finish()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Train line drawing → XYZ map model")

    # Paths
    p.add_argument("--data_root",       type=str, default="./data")
    p.add_argument("--checkpoint_dir",  type=str, default="./checkpoints")
    p.add_argument("--resume",          type=str, default=None, help="Path to checkpoint to resume from")

    # Data
    p.add_argument("--image_size",  type=int, default=256)
    p.add_argument("--batch_size",  type=int, default=16)
    p.add_argument("--num_workers", type=int, default=4)

    # Model
    p.add_argument("--base_features", type=int,   default=64)
    p.add_argument("--depth",         type=int,   default=4)
    p.add_argument("--dropout",       type=float, default=0.2)

    # Training
    p.add_argument("--epochs",       type=int,   default=200)
    p.add_argument("--lr",           type=float, default=2e-4)
    p.add_argument("--weight_decay", type=float, default=1e-4)
    p.add_argument("--patience",     type=int,   default=30,  help="Early stopping patience")

    # Loss weights
    p.add_argument("--w_l1",     type=float, default=1.0)
    p.add_argument("--w_grad",   type=float, default=0.5)
    p.add_argument("--w_normal", type=float, default=0.3)
    p.add_argument("--w_ssim",   type=float, default=0.2)

    # Logging
    p.add_argument("--vis_every",     type=int,  default=10,  help="Save visualizations every N epochs")
    p.add_argument("--save_every",    type=int,  default=50,  help="Save periodic checkpoint every N epochs")
    p.add_argument("--wandb",         action="store_true",    help="Enable Weights & Biases logging")
    p.add_argument("--wandb_project", type=str,  default="xyz-trainer")

    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(args)
