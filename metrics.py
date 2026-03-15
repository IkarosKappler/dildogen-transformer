"""
metrics.py - Evaluation metrics for XYZ coordinate map prediction.

All functions accept batched tensors of shape [B, 3, H, W] in [0, 1].
Call .update() per batch, then .compute() at epoch end.
"""

import torch
import torch.nn.functional as F
from losses import xyz_to_normals


# ---------------------------------------------------------------------------
# Running metric accumulator (avoids storing all predictions in memory)
# ---------------------------------------------------------------------------

class RunningMetrics:
    """
    Accumulates per-batch metrics and computes epoch-level averages.

    Usage:
        metrics = RunningMetrics()
        for pred, target in loader:
            metrics.update(pred, target)
        results = metrics.compute()
        metrics.reset()
    """

    def __init__(self):
        self._sums  = {}
        self._count = 0

    def update(self, pred: torch.Tensor, target: torch.Tensor):
        batch_metrics = compute_all_metrics(pred, target)
        n = pred.shape[0]
        for k, v in batch_metrics.items():
            self._sums[k] = self._sums.get(k, 0.0) + v * n
        self._count += n

    def compute(self) -> dict:
        if self._count == 0:
            return {}
        return {k: v / self._count for k, v in self._sums.items()}

    def reset(self):
        self._sums  = {}
        self._count = 0


# ---------------------------------------------------------------------------
# Individual metric functions
# ---------------------------------------------------------------------------

def mae(pred: torch.Tensor, target: torch.Tensor) -> float:
    """Mean Absolute Error — raw coordinate accuracy."""
    return F.l1_loss(pred, target).item()


def rmse(pred: torch.Tensor, target: torch.Tensor) -> float:
    """Root Mean Squared Error."""
    return torch.sqrt(F.mse_loss(pred, target)).item()


def abs_rel(pred: torch.Tensor, target: torch.Tensor, eps: float = 1e-6) -> float:
    """
    Absolute Relative Error — scale-independent depth metric.
    AbsRel = mean(|pred - target| / target)
    Only meaningful on the Z (depth) channel; computed on all channels here.
    """
    return (torch.abs(pred - target) / (target + eps)).mean().item()


def sq_rel(pred: torch.Tensor, target: torch.Tensor, eps: float = 1e-6) -> float:
    """Squared Relative Error."""
    return (((pred - target) ** 2) / (target + eps)).mean().item()


def delta_accuracy(
    pred:      torch.Tensor,
    target:    torch.Tensor,
    threshold: float = 1.25,
    eps:       float = 1e-6,
) -> float:
    """
    δ < threshold accuracy (standard depth metric).
    Fraction of pixels where max(pred/target, target/pred) < threshold.
    """
    ratio = torch.max(
        pred / (target + eps),
        target / (pred + eps),
    )
    return (ratio < threshold).float().mean().item()


def mean_angle_error(pred: torch.Tensor, target: torch.Tensor) -> float:
    """
    Mean angular error between predicted and target surface normals (degrees).
    """
    pred_n   = xyz_to_normals(pred)
    target_n = xyz_to_normals(target)

    cos_sim = (pred_n * target_n).sum(dim=1).clamp(-1, 1)   # [B, H, W]
    angle_rad = torch.acos(cos_sim)
    return torch.rad2deg(angle_rad).mean().item()


def psnr(pred: torch.Tensor, target: torch.Tensor, max_val: float = 1.0) -> float:
    """Peak Signal-to-Noise Ratio (higher = better)."""
    mse_val = F.mse_loss(pred, target).item()
    if mse_val == 0:
        return float("inf")
    return 10 * torch.log10(torch.tensor(max_val ** 2 / mse_val)).item()


# ---------------------------------------------------------------------------
# Combined metric computation
# ---------------------------------------------------------------------------

def compute_all_metrics(pred: torch.Tensor, target: torch.Tensor) -> dict:
    """
    Compute all metrics for a batch.
    Returns a flat dict of {metric_name: float}.
    """
    with torch.no_grad():
        return {
            "metric/mae":        mae(pred, target),
            "metric/rmse":       rmse(pred, target),
            "metric/abs_rel":    abs_rel(pred, target),
            "metric/sq_rel":     sq_rel(pred, target),
            "metric/delta_1_25": delta_accuracy(pred, target, 1.25),
            "metric/delta_1_10": delta_accuracy(pred, target, 1.10),
            "metric/angle_err":  mean_angle_error(pred, target),
            "metric/psnr":       psnr(pred, target),
        }


# ---------------------------------------------------------------------------
# Sanity check
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pred   = torch.rand(4, 3, 256, 256)
    target = torch.rand(4, 3, 256, 256)

    rm = RunningMetrics()
    rm.update(pred, target)
    results = rm.compute()

    print("Metrics:")
    for k, v in results.items():
        print(f"  {k}: {v:.4f}")
