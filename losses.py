"""
losses.py - Loss functions for XYZ coordinate map regression.

A combined loss that addresses the main failure modes of naive pixel losses:
  - L1 loss:          Robust to outliers, avoids blurry predictions (vs MSE)
  - Gradient loss:    Penalizes discontinuities; enforces smooth surfaces
  - Normal loss:      Penalizes incorrect surface orientation (derived from XYZ)
  - SSIM loss:        Structural similarity; preserves perceptual coherence

All losses operate on tensors of shape [B, 3, H, W] in [0, 1].
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# Gradient loss
# ---------------------------------------------------------------------------

def image_gradients(img: torch.Tensor):
    """
    Compute spatial gradients (dx, dy) for each channel.
    Returns tensors of shape [B, C, H, W].
    """
    # Horizontal gradient (right - center)
    dx = img[:, :, :, 1:] - img[:, :, :, :-1]   # [B, C, H, W-1]
    # Vertical gradient (below - center)
    dy = img[:, :, 1:, :] - img[:, :, :-1, :]   # [B, C, H-1, W]
    return dx, dy


class GradientLoss(nn.Module):
    """
    Penalizes differences in spatial gradients between prediction and target.
    Encourages smooth surfaces and sharp edges in the right places.
    """

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        pred_dx,   pred_dy   = image_gradients(pred)
        target_dx, target_dy = image_gradients(target)
        loss = (
            F.l1_loss(pred_dx, target_dx) +
            F.l1_loss(pred_dy, target_dy)
        )
        return loss


# ---------------------------------------------------------------------------
# Surface normal loss
# ---------------------------------------------------------------------------

def xyz_to_normals(xyz: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    """
    Compute approximate surface normals from an XYZ coordinate map.

    The normal at each pixel is the cross product of the horizontal and
    vertical surface tangent vectors (finite differences).

    Args:
        xyz: [B, 3, H, W] XYZ coordinate map in [0, 1]
    Returns:
        normals: [B, 3, H, W] unit normal vectors (values in [-1, 1])
    """
    # Pad to maintain spatial dimensions
    xyz_pad = F.pad(xyz, (1, 1, 1, 1), mode="replicate")  # [B, 3, H+2, W+2]

    # Tangent vectors
    t_x = xyz_pad[:, :, 1:-1, 2:] - xyz_pad[:, :, 1:-1, :-2]  # horizontal
    t_y = xyz_pad[:, :, 2:, 1:-1] - xyz_pad[:, :, :-2, 1:-1]  # vertical

    # Cross product: normal = t_x × t_y
    nx = t_x[:, 1] * t_y[:, 2] - t_x[:, 2] * t_y[:, 1]
    ny = t_x[:, 2] * t_y[:, 0] - t_x[:, 0] * t_y[:, 2]
    nz = t_x[:, 0] * t_y[:, 1] - t_x[:, 1] * t_y[:, 0]

    normals = torch.stack([nx, ny, nz], dim=1)  # [B, 3, H, W]

    # Normalize to unit length
    norm = torch.norm(normals, dim=1, keepdim=True).clamp(min=eps)
    return normals / norm


class NormalLoss(nn.Module):
    """
    Penalizes angular deviation between predicted and target surface normals.
    Uses cosine distance: 1 - cos(θ) ranges from 0 (perfect) to 2 (opposite).
    """

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        pred_n   = xyz_to_normals(pred)
        target_n = xyz_to_normals(target)

        # Cosine similarity per pixel, then mean
        cos_sim = (pred_n * target_n).sum(dim=1)  # [B, H, W]
        loss = (1.0 - cos_sim).mean()
        return loss


# ---------------------------------------------------------------------------
# SSIM loss
# ---------------------------------------------------------------------------

class SSIMLoss(nn.Module):
    """
    Structural Similarity Index loss.
    Measures luminance, contrast, and structural similarity jointly.
    Applied per-channel and averaged.

    Args:
        window_size: Size of the Gaussian kernel (default 11).
    """

    def __init__(self, window_size: int = 11):
        super().__init__()
        self.window_size = window_size
        self.register_buffer("window", self._gaussian_window(window_size))

    @staticmethod
    def _gaussian_window(size: int, sigma: float = 1.5) -> torch.Tensor:
        coords = torch.arange(size, dtype=torch.float) - size // 2
        g = torch.exp(-(coords ** 2) / (2 * sigma ** 2))
        g /= g.sum()
        kernel = g.outer(g)
        return kernel.unsqueeze(0).unsqueeze(0)   # 1×1×K×K

    def _ssim_channel(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        C1, C2 = 0.01 ** 2, 0.03 ** 2
        w = self.window.to(x.device)

        def conv(t):
            return F.conv2d(t, w, padding=self.window_size // 2, groups=1)

        mu_x  = conv(x);       mu_y  = conv(y)
        mu_xx = conv(x * x);   mu_yy = conv(y * y);   mu_xy = conv(x * y)

        sig_x  = mu_xx - mu_x * mu_x
        sig_y  = mu_yy - mu_y * mu_y
        sig_xy = mu_xy - mu_x * mu_y

        num = (2 * mu_x * mu_y + C1) * (2 * sig_xy + C2)
        den = (mu_x ** 2 + mu_y ** 2 + C1) * (sig_x + sig_y + C2)
        return (num / den).mean()

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        ssim_val = torch.stack([
            self._ssim_channel(pred[:, c:c+1], target[:, c:c+1])
            for c in range(pred.shape[1])
        ]).mean()
        return 1.0 - ssim_val   # convert similarity → loss


# ---------------------------------------------------------------------------
# Combined loss
# ---------------------------------------------------------------------------

class XYZLoss(nn.Module):
    """
    Weighted combination of L1, gradient, normal, and SSIM losses.

    Default weights are a good starting point; tune based on validation metrics.

    Args:
        w_l1:      Weight for pixel-wise L1 loss.
        w_grad:    Weight for gradient smoothness loss.
        w_normal:  Weight for surface normal consistency loss.
        w_ssim:    Weight for SSIM structural loss.
    """

    def __init__(
        self,
        w_l1:     float = 1.0,
        w_grad:   float = 0.5,
        w_normal: float = 0.3,
        w_ssim:   float = 0.2,
    ):
        super().__init__()
        self.w_l1     = w_l1
        self.w_grad   = w_grad
        self.w_normal = w_normal
        self.w_ssim   = w_ssim

        self.grad_loss   = GradientLoss()
        self.normal_loss = NormalLoss()
        self.ssim_loss   = SSIMLoss()

    def forward(
        self,
        pred:   torch.Tensor,
        target: torch.Tensor,
    ) -> tuple[torch.Tensor, dict]:
        """
        Returns:
            total_loss: Scalar tensor for backprop.
            components: Dict of individual loss values (for logging).
        """
        l1     = F.l1_loss(pred, target)
        grad   = self.grad_loss(pred, target)
        normal = self.normal_loss(pred, target)
        ssim   = self.ssim_loss(pred, target)

        total = (
            self.w_l1     * l1     +
            self.w_grad   * grad   +
            self.w_normal * normal +
            self.w_ssim   * ssim
        )

        components = {
            "loss/l1":     l1.item(),
            "loss/grad":   grad.item(),
            "loss/normal": normal.item(),
            "loss/ssim":   ssim.item(),
            "loss/total":  total.item(),
        }
        return total, components


# ---------------------------------------------------------------------------
# Sanity check
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pred   = torch.rand(2, 3, 256, 256)
    target = torch.rand(2, 3, 256, 256)
    criterion = XYZLoss()
    loss, comps = criterion(pred, target)
    print(f"Total loss: {loss.item():.4f}")
    for k, v in comps.items():
        print(f"  {k}: {v:.4f}")
