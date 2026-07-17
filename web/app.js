// Dildogen browser demo: line drawing -> XYZ map -> 3D mesh, fully client-side.
// Inference: ONNX Runtime Web (global `ort`). 3D preview: three.js.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const SIZE = 256;                       // model input/output resolution
const MODEL_URL = "model/dildogen.onnx";

// ---------------------------------------------------------------------------
// Status helper
// ---------------------------------------------------------------------------
const statusEl = document.getElementById("status");
const statusText = document.getElementById("statusText");
function setStatus(state, text) {
  statusEl.className = state;          // "", "ready", "busy", "error"
  statusText.textContent = text;
}

// ---------------------------------------------------------------------------
// Drawing canvas
// ---------------------------------------------------------------------------
const draw = document.getElementById("drawCanvas");
const dctx = draw.getContext("2d", { willReadFrequently: true });
const brush = document.getElementById("brush");

function clearDraw() {
  dctx.fillStyle = "#fff";
  dctx.fillRect(0, 0, SIZE, SIZE);
}
clearDraw();

let drawing = false, lastPt = null;
function canvasPt(e) {
  const r = draw.getBoundingClientRect();
  return { x: (e.clientX - r.left) / r.width * SIZE, y: (e.clientY - r.top) / r.height * SIZE };
}
function strokeTo(p) {
  dctx.strokeStyle = "#000";
  dctx.lineWidth = +brush.value;
  dctx.lineCap = "round";
  dctx.lineJoin = "round";
  dctx.beginPath();
  dctx.moveTo(lastPt.x, lastPt.y);
  dctx.lineTo(p.x, p.y);
  dctx.stroke();
  lastPt = p;
}
draw.addEventListener("pointerdown", (e) => { drawing = true; lastPt = canvasPt(e); draw.setPointerCapture(e.pointerId); });
draw.addEventListener("pointermove", (e) => { if (drawing) strokeTo(canvasPt(e)); });
draw.addEventListener("pointerup", () => { drawing = false; });
draw.addEventListener("pointerleave", () => { drawing = false; });

document.getElementById("clearBtn").addEventListener("click", clearDraw);

// Upload an existing drawing
document.getElementById("fileInput").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const img = new Image();
  img.onload = () => {
    clearDraw();
    // contain-fit into the square canvas
    const s = Math.min(SIZE / img.width, SIZE / img.height);
    const w = img.width * s, h = img.height * s;
    dctx.drawImage(img, (SIZE - w) / 2, (SIZE - h) / 2, w, h);
    URL.revokeObjectURL(img.src);
  };
  img.src = URL.createObjectURL(file);
});

// ---------------------------------------------------------------------------
// ONNX Runtime session
// ---------------------------------------------------------------------------
let session = null;
let backend = "wasm";

async function initSession() {
  // Where ORT fetches its .wasm / jsep assets from.
  ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/";
  ort.env.wasm.numThreads = 1;   // no cross-origin-isolation needed on static hosts

  const tryProviders = [["webgpu", "WebGPU"], ["wasm", "WASM (CPU)"]];
  for (const [ep, label] of tryProviders) {
    try {
      setStatus("busy", `loading model on ${label}…`);
      session = await ort.InferenceSession.create(MODEL_URL, { executionProviders: [ep] });
      backend = ep;
      setStatus("ready", `ready · ${label}`);
      return;
    } catch (err) {
      console.warn(`${ep} unavailable:`, err);
    }
  }
  setStatus("error", "could not load model");
  throw new Error("No working execution provider");
}

// ---------------------------------------------------------------------------
// Pre / post processing
// ---------------------------------------------------------------------------
function drawingToTensor() {
  const { data } = dctx.getImageData(0, 0, SIZE, SIZE);   // RGBA
  const arr = new Float32Array(SIZE * SIZE);
  for (let i = 0; i < SIZE * SIZE; i++) {
    // grayscale (luminance) normalized to [0,1], matching training (PIL "L")
    const r = data[i * 4], g = data[i * 4 + 1], b = data[i * 4 + 2];
    arr[i] = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  }
  return new ort.Tensor("float32", arr, [1, 1, SIZE, SIZE]);
}

// output tensor (planar CHW, [0,1]) -> paints the XYZ canvas
function paintXYZ(out) {
  const xyz = document.getElementById("xyzCanvas");
  const xctx = xyz.getContext("2d");
  const img = xctx.createImageData(SIZE, SIZE);
  const N = SIZE * SIZE;
  for (let i = 0; i < N; i++) {
    img.data[i * 4]     = out[i]         * 255;   // R = X
    img.data[i * 4 + 1] = out[i + N]     * 255;   // G = Y
    img.data[i * 4 + 2] = out[i + 2 * N] * 255;   // B = Z
    img.data[i * 4 + 3] = 255;
  }
  xctx.putImageData(img, 0, 0);
  const dl = document.getElementById("dlPng");
  dl.href = xyz.toDataURL("image/png");
  dl.hidden = false;
}

// ---------------------------------------------------------------------------
// three.js scene
// ---------------------------------------------------------------------------
let renderer, scene, camera, controls, mesh;

function initThree() {
  const canvas = document.getElementById("view3d");
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0c10);
  camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100);
  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  scene.add(new THREE.AmbientLight(0xffffff, 0.7));
  const dir = new THREE.DirectionalLight(0xffffff, 0.8);
  dir.position.set(1, 1, 2);
  scene.add(dir);
  resizeThree();
  new ResizeObserver(resizeThree).observe(canvas);
  resetView();
  (function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();
}

function resizeThree() {
  const c = renderer.domElement;
  const w = c.clientWidth, h = c.clientHeight;
  if (w && h && (c.width !== w || c.height !== h)) {
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
}
function resetView() {
  camera.position.set(0, 0, 2.2);
  camera.lookAt(0, 0, 0);
  if (controls) controls.target.set(0, 0, 0);
}
document.getElementById("resetView").addEventListener("click", resetView);

// Build a grid mesh: vertex position = decoded XYZ, connectivity = pixel grid.
function buildMesh(out) {
  const N = SIZE * SIZE;
  const positions = new Float32Array(N * 3);
  const colors = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    const x = out[i], y = out[i + N], z = out[i + 2 * N];  // [0,1]
    // center around origin so it frames nicely
    positions[i * 3]     = x - 0.5;
    positions[i * 3 + 1] = 0.5 - y;     // flip Y (image rows go top→down)
    positions[i * 3 + 2] = z - 0.5;
    colors[i * 3] = x; colors[i * 3 + 1] = y; colors[i * 3 + 2] = z;
  }
  // two triangles per grid cell
  const cells = (SIZE - 1) * (SIZE - 1);
  const idx = new Uint32Array(cells * 6);
  let k = 0;
  for (let r = 0; r < SIZE - 1; r++) {
    for (let c = 0; c < SIZE - 1; c++) {
      const a = r * SIZE + c, b = a + 1, d = a + SIZE, e = d + 1;
      idx[k++] = a; idx[k++] = b; idx[k++] = e;
      idx[k++] = a; idx[k++] = e; idx[k++] = d;
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  geo.setIndex(new THREE.BufferAttribute(idx, 1));
  geo.computeVertexNormals();

  if (mesh) { scene.remove(mesh); mesh.geometry.dispose(); mesh.material.dispose(); }
  const mat = new THREE.MeshStandardMaterial({ vertexColors: true, side: THREE.DoubleSide, roughness: 0.85, metalness: 0.0 });
  mesh = new THREE.Mesh(geo, mat);
  scene.add(mesh);

  buildObjDownload(positions, colors, idx);
}

// Assemble an .obj (with vertex colors) for download.
function buildObjDownload(positions, colors, idx) {
  const lines = [];
  for (let i = 0; i < positions.length; i += 3) {
    lines.push(`v ${positions[i].toFixed(6)} ${positions[i + 1].toFixed(6)} ${positions[i + 2].toFixed(6)} ` +
               `${colors[i].toFixed(4)} ${colors[i + 1].toFixed(4)} ${colors[i + 2].toFixed(4)}`);
  }
  for (let i = 0; i < idx.length; i += 3) {
    lines.push(`f ${idx[i] + 1} ${idx[i + 1] + 1} ${idx[i + 2] + 1}`);  // OBJ is 1-based
  }
  const blob = new Blob([lines.join("\n") + "\n"], { type: "text/plain" });
  const a = document.getElementById("dlObj");
  if (a.href) URL.revokeObjectURL(a.href);
  a.href = URL.createObjectURL(blob);
  a.hidden = false;
}

// ---------------------------------------------------------------------------
// Generate
// ---------------------------------------------------------------------------
const generateBtn = document.getElementById("generateBtn");
generateBtn.addEventListener("click", async () => {
  if (!session) return;
  generateBtn.disabled = true;
  setStatus("busy", "generating…");
  try {
    const t0 = performance.now();
    const results = await session.run({ line: drawingToTensor() });
    const out = results.xyz.data;                 // Float32Array, planar CHW
    paintXYZ(out);
    buildMesh(out);
    const ms = (performance.now() - t0).toFixed(0);
    setStatus("ready", `done in ${ms} ms · ${backend}`);
  } catch (err) {
    console.error(err);
    setStatus("error", "inference failed (see console)");
  } finally {
    generateBtn.disabled = false;
  }
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
initThree();
initSession()
  .then(() => { generateBtn.disabled = false; })
  .catch(() => {});
