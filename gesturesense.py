import os
import sys
import base64
import logging
import asyncio
import json
import re
import time
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
import requests
from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
VISION_PROVIDER = os.getenv("VISION_PROVIDER", "groq" if GROQ_API_KEY else "gemini").strip().lower()


def _resolve_vision_backend() -> dict[str, str | None]:
    if VISION_PROVIDER == "groq" and GROQ_API_KEY:
        return {"provider": "groq", "api_key": GROQ_API_KEY, "model": GROQ_MODEL}

    if VISION_PROVIDER == "gemini" and GEMINI_API_KEY:
        return {"provider": "gemini", "api_key": GEMINI_API_KEY, "model": GEMINI_MODEL}

    if GROQ_API_KEY:
        return {"provider": "groq", "api_key": GROQ_API_KEY, "model": GROQ_MODEL}

    if GEMINI_API_KEY:
        return {"provider": "gemini", "api_key": GEMINI_API_KEY, "model": GEMINI_MODEL}

    return {"provider": None, "api_key": None, "model": GROQ_MODEL if VISION_PROVIDER == "groq" else GEMINI_MODEL}


VISION_BACKEND = _resolve_vision_backend()


def _resolve_runtime_backend(provider: str | None = None) -> dict[str, str | None]:
    requested = (provider or "auto").strip().lower()

    if requested == "groq":
        return {"provider": "groq", "api_key": GROQ_API_KEY, "model": GROQ_MODEL}

    if requested == "gemini":
        return {"provider": "gemini", "api_key": GEMINI_API_KEY, "model": GEMINI_MODEL}

    return VISION_BACKEND

if VISION_BACKEND["provider"] == "gemini" and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info(f"Gemini API configured with model: {GEMINI_MODEL}")
elif VISION_BACKEND["provider"] == "groq" and GROQ_API_KEY:
    logger.info(f"Groq API configured with model: {GROQ_MODEL}")
else:
    logger.warning("No vision API key configured - detection will fail")

# Initialize FastAPI app
app = FastAPI(
    title="GestureSense API",
    description="Sign Language Detection using vision-capable LLMs",
    version="1.0.0"
)

# Add CORS middleware - Allow frontend to connect from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Called when the server starts."""
    logger.info("✅ GestureSense API Server started successfully")
    logger.info(f"📡 Backend running on 0.0.0.0:8000")
    logger.info(f"🤖 Vision Provider: {VISION_BACKEND['provider'] or 'none'}")
    logger.info(f"🤖 Vision Model: {VISION_BACKEND['model']}")
    if VISION_BACKEND["api_key"]:
        logger.info("🔑 API Key: Configured")
    else:
        logger.warning("⚠️  API Key: Not configured - detection will fail")


@app.on_event("shutdown")
async def shutdown_event():
    """Called when the server shuts down."""
    logger.info("🛑 GestureSense API Server shutting down")


def encode_image_to_base64(file_path: str) -> str:
    """Encode image file to base64 string."""
    with open(file_path, "rb") as image_file:
        return base64.standard_b64encode(image_file.read()).decode("utf-8")


def _strip_data_url_prefix(image_data: str) -> str:
    if image_data.startswith("data:") and "," in image_data:
        return image_data.split(",", 1)[1]
    return image_data


def _coerce_confidence(value: object) -> float:
    if isinstance(value, (int, float)):
        confidence = float(value)
        return confidence * 100.0 if 0.0 <= confidence <= 1.0 else confidence

    if isinstance(value, str):
        match = re.search(r"(\d+(?:\.\d+)?)", value)
        if match:
            confidence = float(match.group(1))
            return confidence * 100.0 if 0.0 <= confidence <= 1.0 else confidence

        mapped = {"high": 92.0, "medium": 67.0, "low": 35.0}
        return mapped.get(value.strip().lower(), 0.0)

    return 0.0


def _parse_detection_text(response_text: str) -> dict:
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()

    payload: dict[str, object] = {}
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            payload = parsed
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = {}

    sign_value = payload.get("sign") or payload.get("detected_sign") or payload.get("interpretation")
    sign = sign_value if isinstance(sign_value, str) and sign_value.strip() else None

    detected_value = payload.get("detected")
    if isinstance(detected_value, bool):
        detected = detected_value
    elif isinstance(detected_value, str):
        detected = detected_value.strip().lower() in {"true", "yes", "1"}
    else:
        detected = sign is not None

    confidence = _coerce_confidence(payload.get("confidence"))
    if detected and confidence <= 0.0:
        confidence = 75.0

    return {
        "detected": detected,
        "sign": sign if detected else None,
        "confidence": confidence,
        "raw": response_text,
    }


def analyze_image(image_data: str, *, is_base64: bool = True, provider: str | None = None) -> dict:
    """Analyze an image and return the frontend-friendly detection payload."""
    started_at = time.perf_counter()
    result = detect_sign_language(image_data, is_base64=is_base64, provider=provider)

    if result.get("status") != "success":
        return {
            "error": result.get("error", "Detection failed."),
            "processing_ms": round((time.perf_counter() - started_at) * 1000, 2),
        }

    payload = _parse_detection_text(str(result.get("detection", "")))
    payload["processing_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
    return payload


def detect_sign_language(image_data: str, is_base64: bool = True, provider: str | None = None) -> dict:
    """
    Detect sign language from image using the configured vision provider.
    
    Args:
        image_data: Base64 encoded image or file path
        is_base64: Whether the image_data is base64 encoded
    
    Returns:
        Dictionary containing detected signs and confidence
    """
    try:
        backend = _resolve_runtime_backend(provider)

        # Check if API key is configured
        if not backend["api_key"] or not backend["provider"]:
            return {
                "status": "error",
                "error": "No vision API key configured. Please add GROQ_API_KEY or GEMINI_API_KEY to your .env file.",
                "model": backend["model"]
            }
        
        # Prepare image payload
        if is_base64:
            image_base64 = _strip_data_url_prefix(image_data)
        else:
            image_base64 = encode_image_to_base64(str(image_data))
        
        prompt = """Analyze this image for sign language gestures.

Return only valid JSON with this shape:
{
  "detected": true or false,
  "sign": string or null,
  "confidence": number from 0 to 100,
  "notes": string
}

If no clear sign is visible, set detected to false, sign to null, and confidence to 0.
Do not include markdown fences or extra commentary.
"""

        if backend["provider"] == "groq":
            message_text = _detect_with_groq(image_base64, prompt)
        elif backend["provider"] == "gemini":
            message_text = _detect_with_gemini(image_base64, prompt)
        else:
            raise RuntimeError("No vision provider is configured.")
        
        return {
            "status": "success",
            "detection": message_text,
            "model": backend["model"],
            "provider": backend["provider"],
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "model": backend["model"],
        }


def _detect_with_gemini(image_base64: str, prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY is not configured.")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    message = model.generate_content([
        {
            "mime_type": "image/jpeg",
            "data": image_base64,
        },
        prompt,
    ])
    return getattr(message, "text", "") or ""


def _detect_with_groq(image_base64: str, prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
                ],
            }
        ],
        "temperature": 0,
        "max_completion_tokens": 1024,
        "top_p": 1,
        "stream": False,
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()

    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("Groq response did not include any choices.")

    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Groq response did not include message content.")

    return content


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "GestureSense Sign Language Detection",
        "model": VISION_BACKEND["model"],
        "provider": VISION_BACKEND["provider"],
    }


@app.get("/health")
async def health():
    """Health status endpoint."""
    model_ready = bool(VISION_BACKEND["api_key"])
    provider = VISION_BACKEND["provider"] or "none"
    return {
        "status": "healthy",
        "service": "GestureSense",
        "model": VISION_BACKEND["model"],
        "provider": provider,
        "model_ready": model_ready,
        "dataset": f"{provider}-vision" if provider != "none" else "unconfigured",
        "samples_trained": 0,
        "classes": 0,
        "csv_present": False,
        "cache_present": False,
        "using_synthetic": not model_ready,
        "warning": None if model_ready else "No vision API key configured; detection is unavailable.",
    }


@app.post("/detect/upload")
@app.post("/detect")
async def detect_from_upload(file: UploadFile = File(...), provider: str | None = None):
    """
    Detect sign language from uploaded image.
    
    Args:
        file: Uploaded image file (JPEG, PNG, etc.)
    
    Returns:
        JSON response with detection results
    """
    try:
        # Validate file type
        allowed_extensions = {"jpg", "jpeg", "png", "gif", "webp"}
        file_extension = Path(file.filename).suffix.lower().lstrip(".")
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {allowed_extensions}"
            )
        
        # Read and encode file
        contents = await file.read()
        image_base64 = base64.standard_b64encode(contents).decode("utf-8")
        
        result = analyze_image(image_base64, is_base64=True, provider=provider)

        if "error" in result:
            return JSONResponse(content={"success": False, "message": result["error"]}, status_code=500)

        return JSONResponse(content={
            "success": True,
            "result": result,
            "message": "Detection completed successfully",
        })
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    provider = websocket.query_params.get("provider")

    try:
        while True:
            message = await websocket.receive_text()

            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON payload."})
                continue

            frame = payload.get("frame")
            if not isinstance(frame, str) or not frame:
                await websocket.send_json({"error": "Missing frame data."})
                continue

            result = await asyncio.to_thread(analyze_image, frame, is_base64=True, provider=provider)
            await websocket.send_json(result)
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception("WebSocket stream failed: %s", e)
        try:
            await websocket.send_json({"error": f"Stream failed: {str(e)}"})
        except Exception:
            pass


@app.post("/detect-base64")
async def detect_from_base64(payload: dict):
    """
    Detect sign language from base64 encoded image.
    
    Args:
        payload: JSON with 'image' key containing base64 data
    
    Returns:
        JSON response with detection results
    """
    try:
        if "image" not in payload:
            raise HTTPException(status_code=400, detail="'image' field is required")
        
        image_data = payload["image"]
        result = detect_sign_language(image_data, is_base64=True)
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["error"])
        
        return JSONResponse(content=result)
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.post("/batch-detect")
async def batch_detect(payload: dict):
    """
    Detect sign language from multiple base64 encoded images.
    
    Args:
        payload: JSON with 'images' key containing list of base64 data
    
    Returns:
        JSON response with detection results for all images
    """
    try:
        if "images" not in payload or not isinstance(payload["images"], list):
            raise HTTPException(
                status_code=400,
                detail="'images' field is required and must be a list"
            )
        
        results = []
        for idx, image_data in enumerate(payload["images"]):
            result = detect_sign_language(image_data, is_base64=True)
            results.append({
                "image_index": idx,
                "result": result
            })
        
        return JSONResponse(content={
            "status": "success",
            "batch_size": len(results),
            "results": results
        })
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting GestureSense API on 0.0.0.0:{port}")
    logger.info(f"Using Vision Provider: {VISION_BACKEND['provider'] or 'none'}")
    logger.info(f"Using Vision Model: {VISION_BACKEND['model']}")
    logger.info(f"Available endpoints:")
    logger.info(f"  GET  http://0.0.0.0:{port}/")
    logger.info(f"  GET  http://0.0.0.0:{port}/health")
    logger.info(f"  POST http://0.0.0.0:{port}/detect")
    logger.info(f"  POST http://0.0.0.0:{port}/detect-base64")
    logger.info(f"  POST http://0.0.0.0:{port}/batch-detect")
    logger.info(f"  GET  http://0.0.0.0:{port}/docs (Swagger UI)")
    uvicorn.run(app, host="0.0.0.0", port=port)
