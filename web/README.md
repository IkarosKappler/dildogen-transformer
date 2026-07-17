# Dildogen web demo

Draw a line drawing in the browser → get the generated XYZ map + an interactive
3D model. Runs the model **entirely client-side** (ONNX Runtime Web, WebGPU with
a WASM/CPU fallback). No backend.

## Files

- `index.html` — UI
- `app.js` — drawing, inference, three.js 3D preview
- `model/dildogen.onnx` — the exported model (regenerate with `python ../export_onnx.py`)

ONNX Runtime Web and three.js load from a CDN, so an internet connection is
needed on first load (the browser then caches them).

## Run locally

From this `web/` folder:

```bash
python -m http.server 8000
```

Then open <http://localhost:8000>. (Open it via the server — `file://` will not
load ES modules or the model.)

Use a WebGPU-capable browser (recent Chrome/Edge, or Safari 18+) for best speed;
otherwise it falls back to WASM/CPU, which is slower but works everywhere.

## Deploy

It's fully static — drop the whole `web/` folder onto any static host:

- **GitHub Pages:** commit the folder and enable Pages, or push to a `gh-pages` branch.
- **Netlify / Cloudflare Pages / Vercel:** point the project at this folder, no build step.

The only requirement is that the host serves `model/dildogen.onnx` (32 MB). All
mainstream static hosts do this fine.

## Regenerate the model

The served `model/dildogen.onnx` is the **fp16** build (~16 MB, half the
download, no visible quality loss — inputs/outputs stay float32 so nothing in
`app.js` changes):

```bash
python ../export_onnx.py --checkpoint ../checkpoints/best.pt --output model/dildogen.onnx --fp16
```

Drop `--fp16` for the full-precision build (~32 MB) if you ever need it.
