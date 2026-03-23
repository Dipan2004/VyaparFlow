"""
backend/main.py
---------------
FastAPI application entry point for NotiFlow Autonomous.

Changes from original:
  - Health check no longer references BEDROCK_MODEL_ID
  - Startup log shows NIM model instead of Bedrock model
  - All routing and middleware is identical to original

Run:
    uvicorn backend.main:app --reload
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# .env loader — must happen BEFORE any app.config import
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=_env_path, override=False)
except ImportError:
    pass

# Ensure project root is on sys.path
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.notification_routes import router as notification_router

app = FastAPI(
    title       = "NotiFlow Autonomous API",
    description = (
        "AI operations assistant for small businesses.\n\n"
        "Converts informal Hinglish business notifications into "
        "structured operations — powered by NVIDIA NIM."
    ),
    version  = "2.0.0",
    docs_url = "/docs",
    redoc_url= "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(notification_router)


@app.get("/health", tags=["Meta"])
async def health():
    """Health check — configuration summary."""
    from app.config import (
        DEMO_MODE, NVIDIA_NIM_MODEL, NVIDIA_NIM_API_KEY,
        GEMINI_API_KEY, EXCEL_SYNC_FILE,
    )
    return {
        "status":         "ok",
        "demo_mode":      DEMO_MODE,
        "nim_model":      NVIDIA_NIM_MODEL,
        "nim_enabled":    bool(NVIDIA_NIM_API_KEY),
        "gemini_enabled": bool(GEMINI_API_KEY),
        "excel_file":     str(EXCEL_SYNC_FILE),
    }


@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")


@app.on_event("startup")
async def on_startup():
    from app.config import DEMO_MODE, NVIDIA_NIM_MODEL, NVIDIA_NIM_API_KEY, EXCEL_SYNC_FILE
    logger.info("=" * 55)
    logger.info("  NotiFlow Autonomous API starting up")
    logger.info("  Demo mode   : %s", DEMO_MODE)
    logger.info("  NIM model   : %s", NVIDIA_NIM_MODEL)
    logger.info("  NIM enabled : %s", bool(NVIDIA_NIM_API_KEY))
    logger.info("  Excel file  : %s", EXCEL_SYNC_FILE)
    logger.info("=" * 55)


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("NotiFlow Autonomous API shutting down.")
