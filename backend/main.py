"""
main.py
FastAPI application entry point — TrustAI backend.

Start with:
    uvicorn main:app --reload
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger("trustai")


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("TrustAI backend starting …")

    # Initialise database tables
    from database.database import init_db
    try:
        init_db()
        logger.info("Database initialised.")
    except Exception as exc:
        logger.error("Database init failed: %s", exc)

    # Create upload directory
    upload_dir = os.getenv("UPLOAD_DIR", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    yield

    # Shutdown
    logger.info("TrustAI backend shutting down.")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="TrustAI API",
    description=(
        "Multimodal Digital Content Trust and Fake Content Detection System. "
        "Analyzes images, videos and URLs for manipulation, AI-generation, and phishing risk."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again.",
        },
    )


# ── Routers ───────────────────────────────────────────────────────────────────

from api.url import router as url_router
from api.image import router as image_router
from api.video import router as video_router
from api.history import router as history_router
from api.auth import router as auth_router

app.include_router(url_router, prefix="/api")
app.include_router(image_router, prefix="/api")
app.include_router(video_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(auth_router, prefix="/api")


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
async def health():
    """Health check — returns backend status and model availability."""
    from services.url_service import _model_artifact as url_model
    from services.image_service import _model as image_model
    from services.video_service import _model as video_model

    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "models": {
            "url_phishing": "loaded" if url_model else "not_loaded",
            "image_detection": "loaded" if image_model else "not_loaded",
            "video_deepfake": "loaded" if video_model else "not_loaded",
        },
        "database": _check_db(),
    }


def _check_db() -> str:
    try:
        from database.database import SessionLocal
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
        return "connected"
    except Exception:
        return "unavailable"
