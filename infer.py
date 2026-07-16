"""
infer.py - Run inference with a trained model.

Supports single images, directories, and batch export.
Optionally decodes the output XYZ map back to real-world coordinates
if you supply the normalization bounds used during data preparation.

Usage:
    # Single image
    python infer.py --checkpoint checkpoints/best.pt --input drawing.png

    # Directory of images → output folder
    python infer.py --checkpoint checkpoints/best.pt --input ./drawings/ --output ./results/

    # Decode to real-world XYZ (requires normalization bounds)
    python infer.py --checkpoint checkpoints/best.pt --input drawing.png \
        --xyz_min -1.0 -1.0 0.0 --xyz_max 1.0 1.0 2.0
"""

import argparse
import os
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from model import UNet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


def load_model(checkpoint_path: str, device: torch.device) -> UNet:
    # weights_only=False: our checkpoints store non-tensor metadata (e.g. a numpy
    # best_val_loss), which PyTorch >=2.6 refuses to unpickle under the default.
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)

    # Recover architecture args from checkpoint if available. best.pt stores them;
    # last.pt does not, so fall back to the config this model was trained with.
    saved_args = ckpt.get("args", {})
    model = UNet(
        in_channels   = 1,
        out_channels  = 3,
        base_features = saved_args.get("base_features", 32),
        depth         = saved_args.get("depth", 4),
        dropout       = 0.0,          # disable at inference
        use_attention = True,
    ).to(device)

    model.load_state_dict(ckpt["model"])
    model.eval()
    return model


def preprocess(image_path: str, image_size: int) -> torch.Tensor:
    """Load a line drawing and prepare it as a model-ready tensor."""
    img = Image.open(image_path).convert("L")     # grayscale
    img = img.resize((image_size, image_size), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0  # [0, 1]
    tensor = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)  # 1×1×H×W
    return tensor


def postprocess(
    output:   torch.Tensor,
    xyz_min:  list | None = None,
    xyz_max:  list | None = None,
) -> tuple[np.ndarray, np.ndarray | None]:
    """
    Convert model output tensor → (rgb_image, xyz_array).

    Args:
        output:   1×3×H×W tensor in [0, 1]
        xyz_min:  [x_min, y_min, z_min] for decoding (optional)
        xyz_max:  [x_max, y_max, z_max] for decoding (optional)

    Returns:
        rgb_img:  H×W×3 uint8 numpy array for saving as PNG
        xyz_arr:  H×W×3 float32 numpy array in real-world units (or None)
    """
    out_np  = output.squeeze(0).permute(1, 2, 0).cpu().numpy()  # H×W×3, [0,1]
    rgb_img = (out_np * 255).clip(0, 255).astype(np.uint8)

    xyz_arr = None
    if xyz_min is not None and xyz_max is not None:
        mn  = np.array(xyz_min, dtype=np.float32)
        mx  = np.array(xyz_max, dtype=np.float32)
        xyz_arr = out_np * (mx - mn) + mn    # denormalize to real-world coords

    return rgb_img, xyz_arr


def collect_image_paths(input_path: str) -> list[Path]:
    p = Path(input_path)
    if p.is_file():
        return [p]
    return sorted(f for f in p.iterdir() if f.suffix.lower() in EXTENSIONS)


# ---------------------------------------------------------------------------
# 3D export
# ---------------------------------------------------------------------------
#
# The XYZ map is a structured grid: pixel (row, col) stores one 3D point in its
# RGB value. That lets us export either a point cloud (one vertex per pixel) or
# a surface mesh (adjacent pixels stitched into triangles).

def _decode_xyz(
    out_np:  np.ndarray,                 # H×W×3 in [0, 1]
    xyz_min: list | None,
    xyz_max: list | None,
) -> np.ndarray:
    """Map the [0,1] network output to coordinates. Real units if bounds given."""
    if xyz_min is not None and xyz_max is not None:
        mn = np.array(xyz_min, dtype=np.float32)
        mx = np.array(xyz_max, dtype=np.float32)
        return out_np * (mx - mn) + mn
    return out_np.astype(np.float32)     # normalized [0,1] cube


def _valid_mask(
    rgb_img:  np.ndarray,                # H×W×3 uint8
    bg_color: list | None,
    bg_tol:   int,
) -> np.ndarray:
    """Boolean H×W mask of points to keep. Drops pixels near bg_color if given."""
    if bg_color is None:
        return np.ones(rgb_img.shape[:2], dtype=bool)
    bg   = np.array(bg_color, dtype=np.int16)
    dist = np.abs(rgb_img.astype(np.int16) - bg).max(axis=2)
    return dist > bg_tol


def export_point_cloud_ply(xyz, rgb_img, mask, stride, path):
    """Write an ASCII .ply point cloud (one colored vertex per kept pixel)."""
    xyz  = xyz[::stride, ::stride].reshape(-1, 3)
    cols = rgb_img[::stride, ::stride].reshape(-1, 3)
    keep = mask[::stride, ::stride].reshape(-1)
    xyz, cols = xyz[keep], cols[keep]

    header = (
        "ply\nformat ascii 1.0\n"
        f"element vertex {len(xyz)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    )
    lines = [
        f"{x:.6f} {y:.6f} {z:.6f} {r} {g} {b}"
        for (x, y, z), (r, g, b) in zip(xyz, cols)
    ]
    Path(path).write_text(header + "\n".join(lines) + "\n")
    return len(xyz)


def export_mesh_obj(xyz, rgb_img, mask, stride, path):
    """
    Write an .obj surface mesh by stitching adjacent grid samples into two
    triangles per cell. Faces touching a masked-out vertex are skipped; the
    (unreferenced) vertices are still written, which viewers ignore.
    """
    xs   = xyz[::stride, ::stride]                     # h2×w2×3
    cs   = rgb_img[::stride, ::stride].astype(np.float32) / 255.0
    keep = mask[::stride, ::stride]
    h2, w2 = xs.shape[:2]

    # Vertices (1-based indices in OBJ), with per-vertex color.
    verts = xs.reshape(-1, 3)
    vcols = cs.reshape(-1, 3)
    vlines = [
        f"v {x:.6f} {y:.6f} {z:.6f} {r:.4f} {g:.4f} {b:.4f}"
        for (x, y, z), (r, g, b) in zip(verts, vcols)
    ]

    idx = np.arange(h2 * w2).reshape(h2, w2) + 1       # OBJ is 1-based
    i00, i01 = idx[:-1, :-1], idx[:-1, 1:]
    i10, i11 = idx[1:, :-1],  idx[1:, 1:]
    cell_ok  = keep[:-1, :-1] & keep[:-1, 1:] & keep[1:, :-1] & keep[1:, 1:]

    def tri_lines(a, b, c):
        a, b, c, m = a[cell_ok], b[cell_ok], c[cell_ok], cell_ok[cell_ok]
        return [f"f {p} {q} {r}" for p, q, r in zip(a.ravel(), b.ravel(), c.ravel())]

    flines  = tri_lines(i00, i01, i11) + tri_lines(i00, i11, i10)

    Path(path).write_text("\n".join(vlines) + "\n" + "\n".join(flines) + "\n")
    return len(verts), len(flines)


# ---------------------------------------------------------------------------
# Inference runner
# ---------------------------------------------------------------------------

@torch.inference_mode()
def run_inference(args):
    device = torch.device(
        "cuda" if torch.cuda.is_available() else
        "mps"  if torch.backends.mps.is_available() else
        "cpu"
    )
    print(f"[Infer] Device: {device}")

    model = load_model(args.checkpoint, device)
    print(f"[Infer] Model loaded from '{args.checkpoint}'")

    image_paths = collect_image_paths(args.input)
    print(f"[Infer] Processing {len(image_paths)} image(s)...")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    t_total = 0.0

    for img_path in image_paths:
        t0 = time.time()

        # Preprocess
        tensor = preprocess(str(img_path), args.image_size).to(device)

        # Forward pass
        output = model(tensor)   # 1×3×H×W

        # Postprocess
        xyz_min = args.xyz_min if args.xyz_min else None
        xyz_max = args.xyz_max if args.xyz_max else None
        rgb_img, xyz_arr = postprocess(output, xyz_min, xyz_max)

        # Save XYZ RGB image
        stem        = img_path.stem
        out_rgb     = output_dir / f"{stem}_xyz.png"
        Image.fromarray(rgb_img).save(out_rgb)

        # Optionally save decoded XYZ as numpy array
        if xyz_arr is not None:
            out_npy = output_dir / f"{stem}_xyz.npy"
            np.save(out_npy, xyz_arr)

        # Optional 3D export (mesh and/or point cloud)
        extra = ""
        if args.export_3d != "none":
            out_np = output.squeeze(0).permute(1, 2, 0).cpu().numpy()  # H×W×3 [0,1]
            xyz    = _decode_xyz(out_np, xyz_min, xyz_max)
            mask   = _valid_mask(rgb_img, args.mask_bg_color, args.mask_bg_tol)
            if args.export_3d in ("obj", "both"):
                nv, nf = export_mesh_obj(
                    xyz, rgb_img, mask, args.stride, output_dir / f"{stem}.obj"
                )
                extra += f"  [obj: {nv} verts / {nf} faces]"
            if args.export_3d in ("ply", "both"):
                npts = export_point_cloud_ply(
                    xyz, rgb_img, mask, args.stride, output_dir / f"{stem}.ply"
                )
                extra += f"  [ply: {npts} pts]"

        elapsed  = time.time() - t0
        t_total += elapsed
        print(f"  {img_path.name} → {out_rgb.name}  ({elapsed*1000:.1f} ms){extra}")

    print(
        f"\nDone. {len(image_paths)} image(s) in {t_total:.2f}s "
        f"({t_total/len(image_paths)*1000:.1f} ms/image)"
    )


# ---------------------------------------------------------------------------
# Visualization: overlay XYZ channels side by side
# ---------------------------------------------------------------------------

def visualize_xyz_channels(xyz_rgb_path: str, save_path: str | None = None):
    """
    Split the XYZ RGB image into individual X, Y, Z channel visualizations
    and save a side-by-side comparison.
    """
    img = np.array(Image.open(xyz_rgb_path))   # H×W×3

    titles = ["X (Red)", "Y (Green)", "Z (Blue)"]
    panels = []
    for c, title in enumerate(titles):
        channel = img[:, :, c]
        # Apply a simple colormap for visual clarity
        colored = np.stack([channel, channel, channel], axis=-1)
        panels.append(colored)

    grid = np.concatenate(panels, axis=1)
    out  = Image.fromarray(grid.astype(np.uint8))

    if save_path:
        out.save(save_path)
        print(f"Channel visualization saved to '{save_path}'")
    else:
        out.show()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Run inference with trained XYZ model")

    p.add_argument("--checkpoint",  type=str, required=True, help="Path to .pt checkpoint")
    p.add_argument("--input",       type=str, required=True, help="Input image or directory")
    p.add_argument("--output",      type=str, default="./inference_results")
    p.add_argument("--image_size",  type=int, default=256)

    # Optional: decode output to real-world coordinates
    p.add_argument(
        "--xyz_min", type=float, nargs=3, default=None,
        metavar=("X_MIN", "Y_MIN", "Z_MIN"),
        help="Minimum XYZ values used for normalization",
    )
    p.add_argument(
        "--xyz_max", type=float, nargs=3, default=None,
        metavar=("X_MAX", "Y_MAX", "Z_MAX"),
        help="Maximum XYZ values used for normalization",
    )

    # 3D export
    p.add_argument(
        "--export_3d", choices=["none", "obj", "ply", "both"], default="none",
        help="Also export 3D geometry: 'obj' surface mesh, 'ply' point cloud, or 'both'",
    )
    p.add_argument(
        "--stride", type=int, default=1,
        help="Grid subsampling for 3D export (2 = quarter the points, lighter files)",
    )
    p.add_argument(
        "--mask_bg_color", type=int, nargs=3, default=None,
        metavar=("R", "G", "B"),
        help="Optional background color to drop from 3D export (these maps have none)",
    )
    p.add_argument(
        "--mask_bg_tol", type=int, default=10,
        help="Per-channel tolerance around --mask_bg_color",
    )

    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_inference(args)
