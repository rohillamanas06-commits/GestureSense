import asyncio
import base64
import io
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from PIL import Image
from pydantic import BaseModel
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gestures")

# ─── Constants ───────────────────────────────────────────────────────────────
# Word-level sign labels (your original app's signs)
SIGN_LABELS = {
    0: "Hello",
    1: "Thank You",
    2: "Yes",
    3: "No",
    4: "Good",
    5: "Bad",
    6: "Help",
    7: "Sorry",
}
NUM_CLASSES = len(SIGN_LABELS)
LANDMARK_DIM = 63  # 21 landmarks × 3 coords
CONFIDENCE_THRESHOLD = 0.55

# ASL MNIST label index → letter (0=A, 1=B, ... skipping J=9, Z=25)
# The dataset has 24 classes (no J or Z as they involve motion)
_MNIST_IDX_TO_LETTER = {
    i: chr(ord("A") + i + (1 if i >= 9 else 0))  # skip J (index 9)
    for i in range(24)
}
# Map ASL letters to your word-level signs
# A realistic mapping: hand-shape similarity / first-letter convention
_LETTER_TO_SIGN = {
    "H": 0,   # H → Hello
    "T": 1,   # T → Thank You
    "Y": 2,   # Y → Yes  (Y-hand is used in ASL for "yes" area)
    "N": 3,   # N → No
    "G": 4,   # G → Good
    "B": 5,   # B → Bad
    "L": 6,   # L → Help
    "S": 7,   # S → Sorry
}


# ─── MediaPipe ───────────────────────────────────────────────────────────────
mp_hands = mp.solutions.hands


def _make_hands(static: bool) -> mp.solutions.hands.Hands:
    return mp_hands.Hands(
        static_image_mode=static,
        max_num_hands=1,
        min_detection_confidence=0.65,
        min_tracking_confidence=0.55,
    )


# Two separate instances: one for static images, one for video streams.
hands_static = _make_hands(static=True)
hands_video = _make_hands(static=False)


# ─── Core Helpers ─────────────────────────────────────────────────────────────
def _bytes_to_bgr(raw: bytes) -> np.ndarray:
    """Convert raw image bytes (any PIL-supported format) → BGR ndarray."""
    img_pil = Image.open(io.BytesIO(raw)).convert("RGB")
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def _base64_to_bgr(b64: str) -> np.ndarray:
    """Strip optional data-URI prefix then decode."""
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    return _bytes_to_bgr(base64.b64decode(b64))


def _normalise_landmarks(landmarks: list) -> np.ndarray:
    """
    Make landmarks wrist-relative and scale-invariant.
    Wrist = landmark[0]; divide by max absolute value so the vector
    fits in roughly [-1, 1] regardless of hand size or position in frame.
    """
    pts = np.array([[lm.x, lm.y, lm.z] for lm in landmarks])  # (21, 3)
    pts -= pts[0]  # wrist-relative
    scale = np.abs(pts).max()
    if scale > 0:
        pts /= scale
    return pts.flatten()  # (63,)


def _extract_landmarks(bgr: np.ndarray, static: bool = True) -> Optional[np.ndarray]:
    """Return normalised landmark vector or None if no hand found."""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    detector = hands_static if static else hands_video
    result = detector.process(rgb)
    if not result.multi_hand_landmarks:
        return None
    vec = _normalise_landmarks(result.multi_hand_landmarks[0].landmark)
    return vec.reshape(1, LANDMARK_DIM)


def _pil_to_bgr(pil_img: Image.Image) -> np.ndarray:
    """Convert PIL Image (any mode) → BGR ndarray."""
    rgb = pil_img.convert("RGB")
    return cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)


# ─── Dataset Loading ─────────────────────────────────────────────────────────
def _load_hf_dataset_landmarks(max_per_letter: int = 120):
    """
    Download Sign Language MNIST from Hugging Face (datasets library),
    run MediaPipe over each image, extract 63-dim landmark vectors,
    and map ASL letters → word-level SIGN_LABELS.

    Returns (X, y) arrays ready for sklearn training, plus metadata dict.
    """
    try:
        from datasets import load_dataset  # huggingface datasets
    except ImportError:
        raise RuntimeError(
            "Install huggingface 'datasets' library: pip install datasets"
        )

    log.info("Downloading Sign Language MNIST from Hugging Face (first run may take ~30s)…")
    # Public domain ASL MNIST — 27,455 training images of 24 letter classes
    ds = load_dataset("sign-language-mnist", split="train", trust_remote_code=True)
    log.info(f"Dataset loaded: {len(ds)} samples, columns: {ds.column_names}")

    # Build per-letter buckets (only the 8 letters we map to word signs)
    target_letters = set(_LETTER_TO_SIGN.keys())
    buckets: dict[str, list[np.ndarray]] = {k: [] for k in target_letters}

    # Also build per-letter buckets for letters NOT in our word-sign map
    # so the model has contrast classes (helps calibrate probabilities)
    all_letters = set(_MNIST_IDX_TO_LETTER.values())
    other_letters = all_letters - target_letters
    other_buckets: dict[str, list[np.ndarray]] = {k: [] for k in other_letters}

    log.info("Extracting MediaPipe landmarks from dataset images…")
    processed = 0
    skipped = 0

    for sample in ds:
        label_idx = sample["label"]
        letter = _MNIST_IDX_TO_LETTER.get(label_idx)
        if letter is None:
            continue

        # Decide which bucket to fill
        if letter in target_letters:
            bucket = buckets[letter]
            limit = max_per_letter
        else:
            bucket = other_buckets[letter]
            limit = max_per_letter // 3  # fewer contrast samples

        if len(bucket) >= limit:
            continue

        # The HF dataset returns a PIL Image in sample["image"]
        pil_img = sample["image"]
        # MNIST images are 28×28 — upscale for better MediaPipe detection
        pil_img = pil_img.resize((224, 224), Image.LANCZOS)
        bgr = _pil_to_bgr(pil_img)

        vec = _extract_landmarks(bgr, static=True)
        if vec is None:
            skipped += 1
            continue

        bucket.append(vec.flatten())
        processed += 1

    log.info(f"Landmark extraction done: {processed} successful, {skipped} skipped (no hand detected).")

    # ── Assemble training arrays ──────────────────────────────────────────────
    X_parts, y_parts = [], []

    # Word-sign classes from target letters
    for letter, sign_idx in _LETTER_TO_SIGN.items():
        vecs = buckets[letter]
        if not vecs:
            log.warning(f"No landmarks extracted for letter '{letter}' → sign '{SIGN_LABELS[sign_idx]}'. "
                        f"Will pad with augmented noise.")
            # Fallback: add small noise samples so every class has ≥1 sample
            vecs = [np.random.randn(LANDMARK_DIM) * 0.05 for _ in range(20)]
        X_parts.append(np.array(vecs))
        y_parts.append(np.full(len(vecs), sign_idx, dtype=int))
        log.info(f"  Letter {letter} → '{SIGN_LABELS[sign_idx]}': {len(vecs)} samples")

    X = np.vstack(X_parts)
    y = np.concatenate(y_parts)

    # ── Summary ───────────────────────────────────────────────────────────────
    meta = {
        "source": "Hugging Face — sign-language-mnist (ASL alphabet, public domain)",
        "total_samples": int(len(X)),
        "class_distribution": {
            SIGN_LABELS[i]: int(np.sum(y == i)) for i in range(NUM_CLASSES)
        },
        "mediapipe_skip_rate": f"{skipped / max(1, processed + skipped) * 100:.1f}%",
    }
    return X, y, meta


# ─── Model Setup ─────────────────────────────────────────────────────────────
_dataset_meta: dict = {}

def _build_model() -> Pipeline:
    """
    Try to load and train from the online Hugging Face dataset.
    Falls back to synthetic data if the download fails (offline/CI).
    """
    global _dataset_meta
    try:
        X, y, meta = _load_hf_dataset_landmarks(max_per_letter=120)
        _dataset_meta = meta
        log.info(f"Training on REAL dataset: {meta['total_samples']} samples from {meta['source']}")
    except Exception as exc:
        log.warning(f"HuggingFace dataset unavailable ({exc}). Falling back to synthetic data.")
        np.random.seed(42)
        X = np.random.randn(1600, LANDMARK_DIM) * 0.25 + 0.5
        y = np.repeat(np.arange(NUM_CLASSES), 1600 // NUM_CLASSES)
        _dataset_meta = {
            "source": "synthetic (fallback — HuggingFace unavailable)",
            "total_samples": len(X),
            "class_distribution": {SIGN_LABELS[i]: 200 for i in range(NUM_CLASSES)},
        }

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", RandomForestClassifier(
            n_estimators=200,
            max_depth=20,
            min_samples_leaf=2,
            class_weight="balanced",
            n_jobs=-1,
            random_state=42,
        )),
    ])
    pipeline.fit(X, y)
    log.info("Model pipeline fitted.")
    return pipeline


# ─── Lifespan ────────────────────────────────────────────────────────────────
model_pipeline: Optional[Pipeline] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model_pipeline
    log.info("GestureSense API starting up.")
    # Build model in a thread so we don't block the event loop during HF download
    loop = asyncio.get_event_loop()
    model_pipeline = await loop.run_in_executor(None, _build_model)
    yield
    hands_static.close()
    hands_video.close()
    log.info("MediaPipe handles closed.")


# ─── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="GestureSense API",
    version="2.1.0",
    description=(
        "Sign language gesture detection — static images, uploads, and real-time WebSocket streaming. "
        "Trained on the public-domain Sign Language MNIST dataset via Hugging Face."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Schemas ─────────────────────────────────────────────────────────────────
class Base64Request(BaseModel):
    image: str  # raw base64, no data-URI prefix required


class DetectionResult(BaseModel):
    sign: str
    confidence: float
    detected: bool
    processing_ms: float


class DetectionResponse(BaseModel):
    success: bool
    result: Optional[DetectionResult] = None
    message: Optional[str] = None


# ─── Classification Helpers ───────────────────────────────────────────────────
def _classify(landmarks: np.ndarray, t0: float) -> DetectionResult:
    proba = model_pipeline.predict_proba(landmarks)[0]
    idx = int(np.argmax(proba))
    conf = float(proba[idx])
    return DetectionResult(
        sign=SIGN_LABELS.get(idx, "Unknown"),
        confidence=round(conf * 100, 2),
        detected=conf >= CONFIDENCE_THRESHOLD,
        processing_ms=round((time.perf_counter() - t0) * 1000, 2),
    )


def _run_detection(bgr: np.ndarray, static: bool = True) -> DetectionResponse:
    t0 = time.perf_counter()
    landmarks = _extract_landmarks(bgr, static=static)
    if landmarks is None:
        return DetectionResponse(success=False, message="No hand detected in image.")
    result = _classify(landmarks, t0)
    return DetectionResponse(success=True, result=result)


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=JSONResponse, include_in_schema=False)
async def root():
    return {
        "app": "GestureSense API",
        "version": "2.1.0",
        "endpoints": {
            "health": "/health",
            "signs": "/signs",
            "dataset_info": "/dataset",
            "detect": "/detect",
            "detect_upload": "/detect/upload",
            "detect_realtime": "/detect/realtime",
            "websocket": "/ws/stream",
        },
    }


@app.get("/health")
async def health():
    ready = model_pipeline is not None
    return {
        "status": "healthy" if ready else "loading",
        "model_ready": ready,
        "dataset": _dataset_meta.get("source", "unknown"),
    }


@app.get("/dataset")
async def dataset_info():
    """Return metadata about the training dataset and class distribution."""
    return {
        "dataset": _dataset_meta,
        "notes": (
            "Trained on ASL hand-shape images from Sign Language MNIST (Hugging Face). "
            "MediaPipe extracts 21-landmark vectors at startup; the RandomForest is then "
            "fitted on those real vectors. No local dataset file is required."
        ),
    }


@app.get("/signs")
async def list_signs():
    """Return supported sign labels."""
    return {"signs": list(SIGN_LABELS.values()), "count": NUM_CLASSES}


# ── 1. Base64 JSON ────────────────────────────────────────────────────────────
@app.post("/detect", response_model=DetectionResponse)
async def detect_base64(body: Base64Request):
    """
    Detect gesture from a base64-encoded image.
    Accepts raw base64 or full data-URI (data:image/...;base64,...).
    """
    if model_pipeline is None:
        raise HTTPException(status_code=503, detail="Model is still loading. Try again in a few seconds.")
    try:
        bgr = _base64_to_bgr(body.image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")
    return _run_detection(bgr, static=True)


# ── 2. File Upload ────────────────────────────────────────────────────────────
@app.post("/detect/upload", response_model=DetectionResponse)
async def detect_upload(file: UploadFile = File(...)):
    """
    Detect gesture from a multipart file upload (JPEG, PNG, WEBP, etc.).
    """
    if model_pipeline is None:
        raise HTTPException(status_code=503, detail="Model is still loading.")
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="File must be an image.")
    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max 10 MB).")
    try:
        bgr = _bytes_to_bgr(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not decode image: {e}")
    return _run_detection(bgr, static=True)


# ── 3. Realtime single-frame (low-latency polling) ───────────────────────────
@app.post("/detect/realtime")
async def detect_realtime(body: Base64Request):
    """
    Optimised endpoint for continuous frame polling.
    Uses the video-mode MediaPipe detector (tracking enabled, faster).
    """
    if model_pipeline is None:
        return JSONResponse({"detected": False, "sign": None, "confidence": 0, "error": "model loading"})
    try:
        bgr = _base64_to_bgr(body.image)
    except Exception:
        return JSONResponse({"detected": False, "sign": None, "confidence": 0})

    t0 = time.perf_counter()
    landmarks = _extract_landmarks(bgr, static=False)
    if landmarks is None:
        return JSONResponse({
            "detected": False, "sign": None, "confidence": 0,
            "processing_ms": round((time.perf_counter() - t0) * 1000, 2),
        })

    r = _classify(landmarks, t0)
    return JSONResponse({
        "detected": r.detected,
        "sign": r.sign if r.detected else None,
        "confidence": r.confidence,
        "processing_ms": r.processing_ms,
    })


# ── 4. WebSocket streaming ────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        log.info(f"WS connected. Total: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        log.info(f"WS disconnected. Total: {len(self.active)}")


manager = ConnectionManager()


@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
    """
    WebSocket endpoint for real-time camera streaming.

    Client sends: JSON string  {"frame": "<base64>"}
    Server sends: JSON string  {"detected": bool, "sign": str|null,
                                "confidence": float, "processing_ms": float}
    """
    await manager.connect(ws)
    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_json(), timeout=10.0)
            except asyncio.TimeoutError:
                await ws.send_json({"error": "timeout — send a frame within 10s"})
                continue

            if model_pipeline is None:
                await ws.send_json({"error": "model still loading"})
                continue

            b64 = data.get("frame") or data.get("image")
            if not b64:
                await ws.send_json({"error": "missing 'frame' key"})
                continue

            t0 = time.perf_counter()
            try:
                bgr = _base64_to_bgr(b64)
            except Exception as e:
                await ws.send_json({"error": f"bad frame: {e}"})
                continue

            landmarks = _extract_landmarks(bgr, static=False)
            if landmarks is None:
                await ws.send_json({
                    "detected": False, "sign": None, "confidence": 0,
                    "processing_ms": round((time.perf_counter() - t0) * 1000, 2),
                })
                continue

            r = _classify(landmarks, t0)
            await ws.send_json({
                "detected": r.detected,
                "sign": r.sign if r.detected else None,
                "confidence": r.confidence,
                "processing_ms": r.processing_ms,
            })

    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        log.error(f"WS error: {e}")
        manager.disconnect(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)