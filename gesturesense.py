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

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info(f"Gemini API configured with model: {GEMINI_MODEL}")
else:
    logger.warning("GEMINI_API_KEY or GOOGLE_API_KEY not set - detection will fail")

# Initialize FastAPI app
app = FastAPI(
    title="GestureSense API",
    description="Sign Language Detection using Gemini Vision",
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
    logger.info(f"🤖 Gemini Model: {GEMINI_MODEL}")
    if GEMINI_API_KEY:
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


def analyze_image(image_data: str, *, is_base64: bool = True) -> dict:
    """Analyze an image and return the frontend-friendly detection payload."""
    started_at = time.perf_counter()
    result = detect_sign_language(image_data, is_base64=is_base64)

    if result.get("status") != "success":
        return {
            "error": result.get("error", "Detection failed."),
            "processing_ms": round((time.perf_counter() - started_at) * 1000, 2),
        }

    payload = _parse_detection_text(str(result.get("detection", "")))
    payload["processing_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
    return payload


def detect_sign_language(image_data: str, is_base64: bool = True) -> dict:
    """
    Detect sign language from image using Gemini Vision.
    
    Args:
        image_data: Base64 encoded image or file path
        is_base64: Whether the image_data is base64 encoded
    
    Returns:
        Dictionary containing detected signs and confidence
    """
    try:
        # Check if API key is configured
        if not GEMINI_API_KEY:
            return {
                "status": "error",
                "error": "GEMINI_API_KEY or GOOGLE_API_KEY not configured. Please add your API key to .env file.",
                "model": GEMINI_MODEL
            }
        
        # Prepare image for Gemini
        if is_base64:
            image_base64 = _strip_data_url_prefix(image_data)
        else:
            image_base64 = encode_image_to_base64(str(image_data))
        
        # Call Gemini Vision API
        model = genai.GenerativeModel(GEMINI_MODEL)
        
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
        
        message = model.generate_content([
            {
                "mime_type": "image/jpeg",
                "data": image_base64,
            },
            prompt
        ])
        
        return {
            "status": "success",
            "detection": message.text,
            "model": GEMINI_MODEL
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "model": GEMINI_MODEL
        }


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "GestureSense Sign Language Detection",
        "model": GEMINI_MODEL
    }


@app.get("/health")
async def health():
    """Health status endpoint."""
    model_ready = bool(GEMINI_API_KEY)
    return {
        "status": "healthy",
        "service": "GestureSense",
        "model": GEMINI_MODEL,
        "model_ready": model_ready,
        "dataset": "gemini-vision",
        "samples_trained": 0,
        "classes": 0,
        "csv_present": False,
        "cache_present": False,
        "using_synthetic": not model_ready,
        "warning": None if model_ready else "API key not configured; detection is unavailable.",
    }


@app.post("/detect/upload")
@app.post("/detect")
async def detect_from_upload(file: UploadFile = File(...)):
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
        
        result = analyze_image(image_base64, is_base64=True)

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

            result = await asyncio.to_thread(analyze_image, frame, is_base64=True)
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
    logger.info(f"Using Gemini Model: {GEMINI_MODEL}")
    logger.info(f"Available endpoints:")
    logger.info(f"  GET  http://0.0.0.0:{port}/")
    logger.info(f"  GET  http://0.0.0.0:{port}/health")
    logger.info(f"  POST http://0.0.0.0:{port}/detect")
    logger.info(f"  POST http://0.0.0.0:{port}/detect-base64")
    logger.info(f"  POST http://0.0.0.0:{port}/batch-detect")
    logger.info(f"  GET  http://0.0.0.0:{port}/docs (Swagger UI)")
    uvicorn.run(app, host="0.0.0.0", port=port)
