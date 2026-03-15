"""
model.py - U-Net architecture for line drawing → XYZ map translation.

The encoder progressively compresses spatial information while the decoder
reconstructs it. Skip connections from encoder to decoder preserve fine
spatial detail — critical for accurate per-pixel XYZ prediction.

Architecture overview:
    Input:  1 × H × W  (grayscale line drawing)
    Output: 3 × H × W  (XYZ map, values in [0, 1])
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

class ConvBlock(nn.Module):
    """Two conv layers with BatchNorm and ReLU. The core U-Net unit."""

    def __init__(self, in_ch: int, out_ch: int, dropout: float = 0.0):
        super().__init__()
        layers = [
            nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        ]
        if dropout > 0:
            layers.append(nn.Dropout2d(dropout))
        self.block = nn.Sequential(*layers)

    def forward(self, x):
        return self.block(x)


class DownBlock(nn.Module):
    """Encoder step: MaxPool2d → ConvBlock."""

    def __init__(self, in_ch: int, out_ch: int, dropout: float = 0.0):
        super().__init__()
        self.pool  = nn.MaxPool2d(2)
        self.conv  = ConvBlock(in_ch, out_ch, dropout)

    def forward(self, x):
        return self.conv(self.pool(x))


class UpBlock(nn.Module):
    """
    Decoder step: upsample → concatenate skip → ConvBlock.
    Uses bilinear upsampling (smoother than transposed conv for coordinate maps).
    """

    def __init__(self, in_ch: int, skip_ch: int, out_ch: int, dropout: float = 0.0):
        super().__init__()
        self.up   = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)
        self.conv = ConvBlock(in_ch + skip_ch, out_ch, dropout)

    def forward(self, x, skip):
        x = self.up(x)
        # Handle size mismatch due to odd input dimensions
        if x.shape != skip.shape:
            x = F.interpolate(x, size=skip.shape[2:], mode="bilinear", align_corners=True)
        x = torch.cat([x, skip], dim=1)
        return self.conv(x)


# ---------------------------------------------------------------------------
# Attention Gate (optional but improves spatial precision)
# ---------------------------------------------------------------------------

class AttentionGate(nn.Module):
    """
    Soft attention gate that selectively highlights relevant skip-connection
    features. Particularly useful for coordinate regression tasks.
    """

    def __init__(self, gate_ch: int, skip_ch: int, inter_ch: int):
        super().__init__()
        self.W_g = nn.Conv2d(gate_ch,  inter_ch, kernel_size=1, bias=False)
        self.W_x = nn.Conv2d(skip_ch,  inter_ch, kernel_size=1, bias=False)
        self.psi = nn.Conv2d(inter_ch, 1,         kernel_size=1, bias=False)
        self.bn  = nn.BatchNorm2d(1)

    def forward(self, gate, skip):
        g = self.W_g(F.interpolate(gate, size=skip.shape[2:], mode="bilinear", align_corners=True))
        x = self.W_x(skip)
        attn = torch.sigmoid(self.bn(self.psi(F.relu(g + x, inplace=True))))
        return skip * attn


# ---------------------------------------------------------------------------
# Main U-Net
# ---------------------------------------------------------------------------

class UNet(nn.Module):
    """
    U-Net for image-to-image coordinate regression.

    Args:
        in_channels:    Number of input channels (1 for grayscale).
        out_channels:   Number of output channels (3 for XYZ).
        base_features:  Feature channels in the first encoder block.
                        Doubles at each level. Default 64 → [64,128,256,512,1024].
        depth:          Number of encoder/decoder levels (4 or 5 recommended).
        dropout:        Dropout rate applied in deeper layers (0.0 = disabled).
        use_attention:  Whether to use attention gates on skip connections.
    """

    def __init__(
        self,
        in_channels:   int   = 1,
        out_channels:  int   = 3,
        base_features: int   = 64,
        depth:         int   = 4,
        dropout:       float = 0.2,
        use_attention: bool  = True,
    ):
        super().__init__()
        self.depth        = depth
        self.use_attention = use_attention

        features = [base_features * (2 ** i) for i in range(depth + 1)]
        # e.g. depth=4: [64, 128, 256, 512, 1024]

        # --- Encoder ---
        self.inc    = ConvBlock(in_channels, features[0])
        self.downs  = nn.ModuleList([
            DownBlock(
                features[i], features[i + 1],
                dropout=dropout if i >= depth // 2 else 0.0,
            )
            for i in range(depth)
        ])

        # --- Attention gates (one per skip connection) ---
        if use_attention:
            self.attns = nn.ModuleList([
                AttentionGate(
                    gate_ch=features[depth - i],
                    skip_ch=features[depth - i - 1],
                    inter_ch=features[depth - i - 1] // 2,
                )
                for i in range(depth)
            ])

        # --- Decoder ---
        self.ups = nn.ModuleList([
            UpBlock(
                in_ch=features[depth - i],
                skip_ch=features[depth - i - 1],
                out_ch=features[depth - i - 1],
                dropout=dropout if i < depth // 2 else 0.0,
            )
            for i in range(depth)
        ])

        # --- Output head ---
        self.outc = nn.Sequential(
            nn.Conv2d(features[0], out_channels, kernel_size=1),
            nn.Sigmoid(),   # clamp output to [0, 1] — matches our XYZ normalization
        )

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Encoder: collect skip connections
        skips = [self.inc(x)]
        for down in self.downs:
            skips.append(down(skips[-1]))

        # Bottleneck is the last skip
        out = skips[-1]

        # Decoder: upsample and merge skips
        for i, up in enumerate(self.ups):
            skip = skips[-(i + 2)]   # corresponding encoder feature
            if self.use_attention:
                skip = self.attns[i](gate=out, skip=skip)
            out = up(out, skip)

        return self.outc(out)

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ---------------------------------------------------------------------------
# Quick sanity check
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    model = UNet(in_channels=1, out_channels=3, base_features=64, depth=4)
    x = torch.randn(2, 1, 256, 256)
    y = model(x)
    print(f"Input:  {x.shape}")
    print(f"Output: {y.shape}")
    print(f"Params: {model.count_parameters():,}")
    assert y.shape == (2, 3, 256, 256), "Shape mismatch!"
    assert y.min() >= 0.0 and y.max() <= 1.0, "Output out of [0,1] range!"
    print("Model OK.")
