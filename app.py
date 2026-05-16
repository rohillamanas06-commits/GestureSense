"""
GestureSense API v2.4 — FastAPI

First run: trains model from CSV, saves model.joblib + landmark cache to project root.
Every run after: loads model.joblib instantly — no retraining.

Retrain triggers automatically if source CSV is newer than saved model.

Training data priority (first file found wins):
  1. landmarks_collected.csv  — webcam-collected data (best)
  2. sign_mnist_train.csv     — Kaggle CSV fallback
  3. Synthetic                — placeholder only, predictions meaningless
"""

import asyncio
import base64
import csv
import io
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import cv2
import joblib
import mediapipe as mp
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from PIL import Image
from pydantic import BaseModel
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gestures")

# ─── Constants ────────────────────────────────────────────────────────────────
_LABEL_TO_LETTER: dict = {i: chr(65 + i) for i in range(26) if i not in (9, 25)}
NUM_CLASSES    = len(_LABEL_TO_LETTER)
LANDMARK_DIM   = 63
CONF_THRESHOLD = 0.45

HERE          = Path(__file__).resolve().parent

# All persistent files live next to app.py
MODEL_PATH    = HERE / "model.joblib"       # trained sklearn pipeline
CACHE_X       = HERE / "mnist_cache_X.npy" # MNIST landmark vectors
CACHE_Y       = HERE / "mnist_cache_y.npy" # MNIST labels

COLLECTED_CSV = HERE / "landmarks_collected.csv"
MNIST_CSV     = HERE / "sign_mnist_train.csv"
FAVICON_PATH  = HERE / "public" / "favicon.ico"

# ─── MediaPipe ────────────────────────────────────────────────────────────────
_mp_hands    = mp.solutions.hands
hands_static = _mp_hands.Hands(
    static_image_mode=True, max_num_hands=1,
    min_detection_confidence=0.60,
)
hands_video = _mp_hands.Hands(
    static_image_mode=False, max_num_hands=1,
    min_detection_confidence=0.60, min_tracking_confidence=0.55,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _normalise(landmarks) -> np.ndarray:
    pts = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float32)
    pts -= pts[0]
    scale = np.abs(pts).max()
    if scale > 0:
        pts /= scale
    return pts.flatten()


def _landmarks_from_bgr(bgr: np.ndarray, static: bool = True) -> Optional[np.ndarray]:
    rgb    = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    result = (hands_static if static else hands_video).process(rgb)
    if not result.multi_hand_landmarks:
        return None
    return _normalise(result.multi_hand_landmarks[0].landmark).reshape(1, LANDMARK_DIM)


def _bytes_to_bgr(raw: bytes) -> np.ndarray:
    return cv2.cvtColor(
        np.array(Image.open(io.BytesIO(raw)).convert("RGB")), cv2.COLOR_RGB2BGR
    )


def _b64_to_bgr(b64: str) -> np.ndarray:
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    return _bytes_to_bgr(base64.b64decode(b64))


# ─── Staleness check ──────────────────────────────────────────────────────────
def _model_is_stale() -> bool:
    """
    Returns True if saved model doesn't exist or source data is newer than model.
    When True, we retrain. When False, we load from disk.
    """
    if not MODEL_PATH.exists():
        log.info("No saved model found — will train.")
        return True

    model_mtime = MODEL_PATH.stat().st_mtime

    # Check if any source CSV is newer than the saved model
    for src in [COLLECTED_CSV, MNIST_CSV]:
        if src.exists() and src.stat().st_mtime > model_mtime:
            log.info("Source file %s is newer than saved model — will retrain.", src.name)
            return True

    log.info("Saved model is up to date — loading from disk.")
    return False


# ─── Dataset loaders ──────────────────────────────────────────────────────────
def _load_collected_csv() -> tuple[np.ndarray, np.ndarray]:
    rows = []
    with open(COLLECTED_CSV, newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            rows.append(row)

    if len(rows) < 10:
        raise ValueError(f"Only {len(rows)} samples — collect more data.")

    X = np.array([[float(v) for v in row[1:]] for row in rows], dtype=np.float32)
    y = np.array([int(row[0]) for row in rows], dtype=np.int32)
    log.info("Loaded %d webcam landmark samples from %s.", len(X), COLLECTED_CSV.name)
    return X, y


def _load_mnist_csv() -> tuple[np.ndarray, np.ndarray]:
    # Check cache — but only if cache is not older than the CSV
    if CACHE_X.exists() and CACHE_Y.exists():
        cache_mtime = CACHE_X.stat().st_mtime
        csv_mtime   = MNIST_CSV.stat().st_mtime
        if cache_mtime >= csv_mtime:
            log.info("MNIST landmark cache hit — loading from project root.")
            X = np.load(str(CACHE_X))
            y = np.load(str(CACHE_Y))
            log.info("Loaded %d cached samples.", len(X))
            return X, y
        else:
            log.info("CSV is newer than cache — rebuilding landmark cache.")

    log.info("Processing sign_mnist_train.csv — this runs ONCE (~5–10 min)...")
    rows = []
    with open(MNIST_CSV, newline="") as f:
        reader = csv.reader(f)
        next(reader)
        rows = list(reader)

    total = len(rows)
    X_list, y_list, skipped = [], [], 0
    t0 = time.perf_counter()

    with _mp_hands.Hands(
        static_image_mode=True, max_num_hands=1, min_detection_confidence=0.50
    ) as det:
        for i, row in enumerate(rows):
            if i > 0 and i % 2000 == 0:
                elapsed   = time.perf_counter() - t0
                remaining = (total - i) / (i / elapsed)
                log.info("  %d/%d | skipped %d | ETA ~%dm%ds",
                         i, total, skipped, int(remaining // 60), int(remaining % 60))

            label  = int(row[0])
            pixels = np.array([int(p) for p in row[1:]], dtype=np.uint8).reshape(28, 28)
            pil    = Image.fromarray(pixels, mode="L").convert("RGB").resize((128, 128), Image.LANCZOS)
            res    = det.process(np.array(pil))

            if not res.multi_hand_landmarks:
                skipped += 1
                continue
            X_list.append(_normalise(res.multi_hand_landmarks[0].landmark))
            y_list.append(label)

    kept = len(X_list)
    log.info("Done: %d kept, %d skipped (%.1f%%).", kept, skipped,
             100 * skipped / max(1, kept + skipped))

    if kept < 100:
        raise ValueError(f"Only {kept} landmarks extracted — too few to use.")

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list,  dtype=np.int32)

    # Save cache to project root
    np.save(str(CACHE_X), X)
    np.save(str(CACHE_Y), y)
    log.info("MNIST landmark cache saved to project root (%s, %s).", CACHE_X.name, CACHE_Y.name)
    return X, y


def _synthetic() -> tuple[np.ndarray, np.ndarray]:
    log.warning("SYNTHETIC DATA — predictions are meaningless. Add real CSV data.")
    np.random.seed(42)
    labels = list(_LABEL_TO_LETTER.keys())
    return (
        np.random.randn(len(labels) * 80, LANDMARK_DIM).astype(np.float32) * 0.25 + 0.5,
        np.repeat(labels, 80).astype(np.int32),
    )


# ─── Model builder ────────────────────────────────────────────────────────────
_dataset_source  = "unknown"
_dataset_samples = 0
_using_real_data = False


def _train_and_save() -> Pipeline:
    global _dataset_source, _dataset_samples, _using_real_data

    X, y = None, None

    if COLLECTED_CSV.exists():
        try:
            X, y = _load_collected_csv()
            _dataset_source  = f"Webcam collected ({COLLECTED_CSV.name})"
            _using_real_data = True
        except Exception as e:
            log.warning("Could not load collected CSV: %s", e)

    if X is None and MNIST_CSV.exists():
        try:
            X, y = _load_mnist_csv()
            _dataset_source  = "Sign Language MNIST (Kaggle)"
            _using_real_data = True
        except Exception as e:
            log.warning("Could not load MNIST CSV: %s", e)

    if X is None:
        X, y = _synthetic()
        _dataset_source  = "SYNTHETIC — add real CSV for real results"
        _using_real_data = False

    _dataset_samples = len(X)

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(
            n_estimators=200,
            max_depth=None,
            min_samples_leaf=1,
            n_jobs=-1,
            random_state=42,
        )),
    ])
    pipe.fit(X, y)
    log.info("Model trained: %d samples, %d classes. Source: %s",
             _dataset_samples, len(pipe.classes_), _dataset_source)

    # Save model to project root
    joblib.dump(pipe, str(MODEL_PATH))
    log.info("Model saved to %s — future startups will load this instantly.", MODEL_PATH.name)
    return pipe


def _load_saved_model() -> Pipeline:
    global _dataset_source, _dataset_samples, _using_real_data
    pipe = joblib.load(str(MODEL_PATH))
    _dataset_source  = "Loaded from saved model (model.joblib)"
    _dataset_samples = -1   # unknown without reprocessing CSV
    _using_real_data = True
    log.info("Model loaded from disk in <1s. Classes: %d", len(pipe.classes_))
    return pipe


def _get_model() -> Pipeline:
    """Load from disk if up-to-date, otherwise retrain and save."""
    if _model_is_stale():
        return _train_and_save()
    return _load_saved_model()


# ─── Lifespan ─────────────────────────────────────────────────────────────────
model_pipeline: Optional[Pipeline] = None
model_classes:  Optional[np.ndarray] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_pipeline, model_classes
    log.info("GestureSense starting up...")

    if not COLLECTED_CSV.exists() and not MNIST_CSV.exists() and not MODEL_PATH.exists():
        log.warning("=" * 60)
        log.warning("No training data or saved model found — using SYNTHETIC data.")
        log.warning("Add sign_mnist_train.csv to project root for real results.")
        log.warning("=" * 60)

    model_pipeline = await asyncio.get_event_loop().run_in_executor(None, _get_model)
    model_classes  = model_pipeline.classes_
    log.info("Model ready. API is live.")
    yield
    hands_static.close()
    hands_video.close()
    log.info("Shut down.")


# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="GestureSense API",
    version="2.4.0",
    description="ASL gesture detection. First run trains & saves model. Subsequent runs load instantly.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ─── Schemas ──────────────────────────────────────────────────────────────────
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


# ─── Classification ───────────────────────────────────────────────────────────
def _classify(lm: np.ndarray, t0: float) -> DetectionResult:
    proba    = model_pipeline.predict_proba(lm)[0]
    best_pos = int(np.argmax(proba))
    conf     = float(proba[best_pos])
    sign     = _LABEL_TO_LETTER.get(int(model_classes[best_pos]), "?")
    return DetectionResult(
        sign=sign,
        confidence=round(conf * 100, 2),
        detected=conf >= CONF_THRESHOLD,
        processing_ms=round((time.perf_counter() - t0) * 1000, 2),
    )


def _detect(bgr: np.ndarray, static: bool = True) -> DetectionResponse:
    t0 = time.perf_counter()
    lm = _landmarks_from_bgr(bgr, static)
    if lm is None:
        return DetectionResponse(success=False, message="No hand detected in image.")
    return DetectionResponse(success=True, result=_classify(lm, t0))


def _check_ready():
    if model_pipeline is None:
        raise HTTPException(503, "Model still loading — retry in a few seconds.")


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    try:
        return open(HERE / "static" / "index.html").read()
    except FileNotFoundError:
        return HTMLResponse(
            "<h2>GestureSense API v2.4</h2>"
            "<p><a href='/docs'>/docs</a> — API reference</p>"
            "<p><a href='/health'>/health</a> — Model status</p>"
        )


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon",     include_in_schema=False)
async def favicon():
    if not FAVICON_PATH.exists():
        raise HTTPException(404, "Favicon not found")
    return FileResponse(str(FAVICON_PATH), media_type="image/x-icon")


@app.get("/health")
async def health():
    return {
        "status":           "healthy" if model_pipeline else "loading",
        "model_ready":      model_pipeline is not None,
        "using_real_data":  _using_real_data,
        "dataset":          _dataset_source,
        "samples_trained":  _dataset_samples,
        "classes":          NUM_CLASSES,
        "data_files": {
            "collected_csv":    COLLECTED_CSV.exists(),
            "mnist_csv":        MNIST_CSV.exists(),
            "saved_model":      MODEL_PATH.exists(),
            "landmark_cache":   CACHE_X.exists() and CACHE_Y.exists(),
        },
    }


@app.get("/signs")
async def signs():
    return {
        "signs": list(_LABEL_TO_LETTER.values()),
        "count": NUM_CLASSES,
        "note":  "ASL A–Y excluding J and Z (motion signs)",
    }


@app.post("/detect", response_model=DetectionResponse)
async def detect_base64(body: Base64Request):
    _check_ready()
    try:
        bgr = _b64_to_bgr(body.image)
    except Exception as e:
        raise HTTPException(400, f"Bad image data: {e}")
    return _detect(bgr, static=True)


@app.post("/detect/upload", response_model=DetectionResponse)
async def detect_upload(file: UploadFile = File(...)):
    _check_ready()
    if not file.content_type.startswith("image/"):
        raise HTTPException(415, "File must be an image.")
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "Max file size is 10 MB.")
    try:
        bgr = _bytes_to_bgr(raw)
    except Exception as e:
        raise HTTPException(400, f"Cannot decode image: {e}")
    return _detect(bgr, static=True)


@app.post("/detect/realtime")
async def detect_realtime(body: Base64Request):
    if model_pipeline is None:
        return JSONResponse({"detected": False, "sign": None,
                             "confidence": 0, "error": "model loading"})
    try:
        bgr = _b64_to_bgr(body.image)
    except Exception:
        return JSONResponse({"detected": False, "sign": None, "confidence": 0})

    t0 = time.perf_counter()
    lm = _landmarks_from_bgr(bgr, static=False)
    ms = round((time.perf_counter() - t0) * 1000, 2)

    if lm is None:
        return JSONResponse({"detected": False, "sign": None,
                             "confidence": 0, "processing_ms": ms})
    r = _classify(lm, t0)
    return JSONResponse({
        "detected":      r.detected,
        "sign":          r.sign if r.detected else None,
        "confidence":    r.confidence,
        "processing_ms": r.processing_ms,
    })


_ws_clients: list = []

@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
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
            ms = round((time.perf_counter() - t0) * 1000, 2)

            if lm is None:
                await ws.send_json({"detected": False, "sign": None,
                                    "confidence": 0, "processing_ms": ms})
                continue

            r = _classify(lm, t0)
            await ws.send_json({
                "detected":      r.detected,
                "sign":          r.sign if r.detected else None,
                "confidence":    r.confidence,
                "processing_ms": r.processing_ms,
            })

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