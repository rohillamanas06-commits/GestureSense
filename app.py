"""
GestureSense API v2.1 — FastAPI
Real-time ASL gesture detection via MediaPipe + RandomForest.

Dataset: Voxel51/American-Sign-Language-MNIST (HuggingFace, public, no login)
  - 34k images of 24 ASL letters (A-Y, excluding J and Z which need motion)
  - First startup: downloads + extracts MediaPipe landmarks (~60-120s)
  - After that: loads from ~/.cache/gestures_sense/ (~3s)
"""

import asyncio
import base64
import io
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from PIL import Image
from pydantic import BaseModel
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gestures")

# ASL MNIST: 24 classes, A-Y excluding J(9) and Z(25)
_LABEL_TO_LETTER: dict = {i: chr(65 + i) for i in range(26) if i not in (9, 25)}
NUM_CLASSES    = len(_LABEL_TO_LETTER)
LANDMARK_DIM   = 63
CONF_THRESHOLD = 0.50

CACHE_DIR = Path.home() / ".cache" / "gestures_sense"
CACHE_X   = CACHE_DIR / "X.npy"
CACHE_Y   = CACHE_DIR / "y.npy"

_mp_hands    = mp.solutions.hands
hands_static = _mp_hands.Hands(static_image_mode=True,  max_num_hands=1, min_detection_confidence=0.60)
hands_video  = _mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.60, min_tracking_confidence=0.50)


def _normalise(landmarks) -> np.ndarray:
    pts = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float32)
    pts -= pts[0]
    scale = np.abs(pts).max()
    if scale > 0:
        pts /= scale
    return pts.flatten()


def _landmarks_from_bgr(bgr: np.ndarray, static: bool = True):
    rgb    = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    result = (hands_static if static else hands_video).process(rgb)
    if not result.multi_hand_landmarks:
        return None
    return _normalise(result.multi_hand_landmarks[0].landmark).reshape(1, LANDMARK_DIM)


def _bytes_to_bgr(raw: bytes) -> np.ndarray:
    return cv2.cvtColor(np.array(Image.open(io.BytesIO(raw)).convert("RGB")), cv2.COLOR_RGB2BGR)

def _b64_to_bgr(b64: str) -> np.ndarray:
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    return _bytes_to_bgr(base64.b64decode(b64))


def _build_dataset():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ── Fast path: landmark cache already exists ──────────────────────────────
    if CACHE_X.exists() and CACHE_Y.exists():
        log.info("Cache hit — loading landmarks from %s (no network calls)", CACHE_DIR)
        X = np.load(str(CACHE_X))
        y = np.load(str(CACHE_Y))
        log.info("Loaded %d samples from cache.", len(X))
        return X, y

    # ── Slow path: first run only ─────────────────────────────────────────────
    # Download Sign Language MNIST as CSV directly from GitHub (raw).
    # 2 HTTP requests total — no API, no rate limiting, no HuggingFace auth.
    # Each row = label + 784 pixel values (28x28 grayscale image).
    import urllib.request

    TRAIN_URL = (
        "https://raw.githubusercontent.com/gchilingaryan/Sign-Language/master/sign_mnist_train.csv"
    )
    FALLBACK_URL = (
        "https://raw.githubusercontent.com/Idodox/HandRecognition/master/sign_mnist_train.csv"
    )

    csv_path = CACHE_DIR / "sign_mnist_train.csv"

    if not csv_path.exists():
        log.info("Downloading Sign Language MNIST CSV (~5 MB)...")
        try:
            urllib.request.urlretrieve(TRAIN_URL, str(csv_path))
            log.info("Download complete.")
        except Exception as e1:
            log.warning("Primary URL failed (%s), trying fallback...", e1)
            try:
                urllib.request.urlretrieve(FALLBACK_URL, str(csv_path))
                log.info("Fallback download complete.")
            except Exception as e2:
                log.warning("Both URLs failed (%s). Using synthetic fallback.", e2)
                return _synthetic()

    # ── Parse CSV ─────────────────────────────────────────────────────────────
    try:
        import csv
        rows = []
        with open(csv_path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)  # skip header row
            for row in reader:
                rows.append(row)
        log.info("CSV loaded: %d rows.", len(rows))
    except Exception as e:
        log.warning("CSV parse failed (%s). Using synthetic fallback.", e)
        return _synthetic()

    # ── Extract MediaPipe landmarks from pixel data ───────────────────────────
    log.info("Extracting MediaPipe landmarks from %d images...", len(rows))
    X_list, y_list, skipped = [], [], 0

    with _mp_hands.Hands(static_image_mode=True, max_num_hands=1,
                         min_detection_confidence=0.50) as det:
        for i, row in enumerate(rows):
            if i % 3000 == 0:
                log.info("  %d / %d  (skipped %d)", i, len(rows), skipped)

            label = int(row[0])
            pixels = np.array([int(p) for p in row[1:]], dtype=np.uint8).reshape(28, 28)

            # Upscale: 28x28 is too small for MediaPipe hand detection
            pil = Image.fromarray(pixels, mode="L").convert("RGB").resize((128, 128), Image.LANCZOS)
            res = det.process(np.array(pil))

            if not res.multi_hand_landmarks:
                skipped += 1
                continue

            X_list.append(_normalise(res.multi_hand_landmarks[0].landmark))
            y_list.append(label)

    kept = len(X_list)
    log.info("Done: %d kept, %d skipped (%.1f%% skip rate).",
             kept, skipped, 100 * skipped / max(1, kept + skipped))

    if kept < 50:
        log.warning("Too few landmarks extracted — synthetic fallback.")
        return _synthetic()

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list,  dtype=np.int32)
    np.save(str(CACHE_X), X)
    np.save(str(CACHE_Y), y)
    log.info("Landmark cache saved to %s — future startups load instantly.", CACHE_DIR)
    return X, y


def _synthetic():
    log.warning("SYNTHETIC DATA — predictions are not meaningful.")
    np.random.seed(42)
    labels = list(_LABEL_TO_LETTER.keys())
    return (np.random.randn(len(labels)*80, LANDMARK_DIM).astype(np.float32)*0.25+0.5,
            np.repeat(labels, 80).astype(np.int32))


_dataset_source  = "unknown"
_dataset_samples = 0

def _train_model() -> Pipeline:
    global _dataset_source, _dataset_samples
    try:
        X, y           = _build_dataset()
        _dataset_source  = "Voxel51/American-Sign-Language-MNIST (HuggingFace)"
        _dataset_samples = len(X)
    except Exception as e:
        log.warning("Dataset failed (%s) — synthetic fallback.", e)
        X, y           = _synthetic()
        _dataset_source  = "synthetic fallback"
        _dataset_samples = len(X)

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(n_estimators=150, max_depth=25,
                                       min_samples_leaf=1, n_jobs=-1, random_state=42)),
    ])
    pipe.fit(X, y)
    log.info("Model trained: %d samples, %d classes.", _dataset_samples, len(pipe.classes_))
    return pipe


model_pipeline = None
model_classes  = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_pipeline, model_classes
    log.info("GestureSense starting up...")
    model_pipeline = await asyncio.get_event_loop().run_in_executor(None, _train_model)
    model_classes  = model_pipeline.classes_
    yield
    hands_static.close()
    hands_video.close()
    log.info("Shut down.")


app = FastAPI(title="GestureSense API", version="2.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FAVICON_PATH = Path(__file__).resolve().parent / "public" / "favicon.ico"


class Base64Request(BaseModel):
    image: str

class DetectionResult(BaseModel):
    sign: str
    confidence: float
    detected: bool
    processing_ms: float

class DetectionResponse(BaseModel):
    success: bool
    result: Optional[DetectionResult] = None
    message: Optional[str] = None


def _classify(lm: np.ndarray, t0: float) -> DetectionResult:
    proba    = model_pipeline.predict_proba(lm)[0]
    best_pos = int(np.argmax(proba))
    conf     = float(proba[best_pos])
    sign     = _LABEL_TO_LETTER.get(int(model_classes[best_pos]), "?")
    return DetectionResult(sign=sign, confidence=round(conf*100, 2),
                           detected=conf >= CONF_THRESHOLD,
                           processing_ms=round((time.perf_counter()-t0)*1000, 2))

def _detect(bgr: np.ndarray, static: bool = True) -> DetectionResponse:
    t0 = time.perf_counter()
    lm = _landmarks_from_bgr(bgr, static)
    if lm is None:
        return DetectionResponse(success=False, message="No hand detected.")
    return DetectionResponse(success=True, result=_classify(lm, t0))

def _check_ready():
    if model_pipeline is None:
        raise HTTPException(503, "Model still loading — retry in a few seconds.")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    try:
        return open("static/index.html").read()
    except FileNotFoundError:
        return HTMLResponse("<h2>GestureSense API running. See <a href='/docs'>/docs</a></h2>")

@app.get("/health")
async def health():
    return {"status": "healthy" if model_pipeline else "loading",
            "model_ready": model_pipeline is not None,
            "dataset": _dataset_source,
            "samples_trained": _dataset_samples,
            "classes": NUM_CLASSES}


@app.get("/favicon")
@app.get("/favicon.ico")
async def favicon():
    if not FAVICON_PATH.exists():
        raise HTTPException(status_code=404, detail="Favicon not found")
    return FileResponse(str(FAVICON_PATH), media_type="image/x-icon")

@app.get("/signs")
async def signs():
    return {"signs": list(_LABEL_TO_LETTER.values()), "count": NUM_CLASSES,
            "note": "ASL A-Y excluding J and Z (motion signs)"}

@app.post("/detect", response_model=DetectionResponse)
async def detect_base64(body: Base64Request):
    """POST {"image": "<base64>"} — raw base64 or data-URI."""
    _check_ready()
    try:
        bgr = _b64_to_bgr(body.image)
    except Exception as e:
        raise HTTPException(400, f"Bad image: {e}")
    return _detect(bgr, static=True)

@app.post("/detect/upload", response_model=DetectionResponse)
async def detect_upload(file: UploadFile = File(...)):
    """Multipart file upload — JPEG, PNG, WEBP, etc."""
    _check_ready()
    if not file.content_type.startswith("image/"):
        raise HTTPException(415, "File must be an image.")
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "Max 10 MB.")
    try:
        bgr = _bytes_to_bgr(raw)
    except Exception as e:
        raise HTTPException(400, f"Cannot decode: {e}")
    return _detect(bgr, static=True)

@app.post("/detect/realtime")
async def detect_realtime(body: Base64Request):
    """Low-latency polling endpoint for webcam frames."""
    if model_pipeline is None:
        return JSONResponse({"detected": False, "sign": None, "confidence": 0, "error": "model loading"})
    try:
        bgr = _b64_to_bgr(body.image)
    except Exception:
        return JSONResponse({"detected": False, "sign": None, "confidence": 0})
    t0 = time.perf_counter()
    lm = _landmarks_from_bgr(bgr, static=False)
    ms = round((time.perf_counter()-t0)*1000, 2)
    if lm is None:
        return JSONResponse({"detected": False, "sign": None, "confidence": 0, "processing_ms": ms})
    r = _classify(lm, t0)
    return JSONResponse({"detected": r.detected, "sign": r.sign if r.detected else None,
                         "confidence": r.confidence, "processing_ms": r.processing_ms})

_ws_clients: list = []

@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    """
    Client sends:  {"frame": "<base64 jpeg>"}
    Server sends:  {"detected": bool, "sign": str|null, "confidence": float, "processing_ms": float}
    """
    await ws.accept()
    _ws_clients.append(ws)
    log.info("WS connected. Active: %d", len(_ws_clients))
    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_json(), timeout=10.0)
            except asyncio.TimeoutError:
                await ws.send_json({"error": "timeout"})
                continue
            if model_pipeline is None:
                await ws.send_json({"error": "model loading"})
                continue
            b64 = data.get("frame") or data.get("image")
            if not b64:
                await ws.send_json({"error": "missing 'frame' key"})
                continue
            t0 = time.perf_counter()
            try:
                bgr = _b64_to_bgr(b64)
            except Exception as e:
                await ws.send_json({"error": f"bad frame: {e}"})
                continue
            lm = _landmarks_from_bgr(bgr, static=False)
            ms = round((time.perf_counter()-t0)*1000, 2)
            if lm is None:
                await ws.send_json({"detected": False, "sign": None, "confidence": 0, "processing_ms": ms})
                continue
            r = _classify(lm, t0)
            await ws.send_json({"detected": r.detected, "sign": r.sign if r.detected else None,
                                "confidence": r.confidence, "processing_ms": r.processing_ms})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error("WS error: %s", e)
    finally:
        if ws in _ws_clients:
            _ws_clients.remove(ws)
        log.info("WS disconnected. Active: %d", len(_ws_clients))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)