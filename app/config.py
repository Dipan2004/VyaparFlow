"""
app/config.py
-------------
Central configuration for NotiFlow Autonomous.

All file paths, feature flags, and model settings live here.
Every other module imports from this file — no hardcoded paths elsewhere.

CHANGED from original:
  - Removed: BEDROCK_REGION, BEDROCK_MODEL_ID (AWS Bedrock fully removed)
  - Added:   NVIDIA_NIM_API_KEY, NVIDIA_NIM_BASE_URL, NVIDIA_NIM_MODEL
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent.parent   # notiflow/

# ---------------------------------------------------------------------------
# Data paths
# ---------------------------------------------------------------------------

DATA_DIR      = ROOT / "data"
DATA_FILE     = DATA_DIR / "notiflow_data.xlsx"
MEMORY_FILE   = DATA_DIR / "agent_memory.json"
REGISTRY_FILE = ROOT / "skills" / "skill_registry.json"

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------

NOTIFLOW_DEMO_MODE = os.getenv("NOTIFLOW_DEMO_MODE", "true").lower() == "true"
DEMO_MODE = NOTIFLOW_DEMO_MODE  # legacy alias

# ---------------------------------------------------------------------------
# NVIDIA NIM settings  (replaces AWS Bedrock)
# ---------------------------------------------------------------------------

NVIDIA_NIM_API_KEY : str | None = (
    os.getenv("NVIDIA_NIM_API_KEY") or os.getenv("NVIDIA_API_KEY")
)
NVIDIA_NIM_BASE_URL: str        = (
    os.getenv("NVIDIA_NIM_BASE_URL")
    or os.getenv("NIM_BASE_URL")
    or "https://integrate.api.nvidia.com/v1"
)
# Legacy single-model override (Phase 1-3 compat)
NVIDIA_NIM_MODEL   : str        = os.getenv(
    "NVIDIA_NIM_MODEL", "deepseek-ai/deepseek-v3.2"
)
# Phase 4: per-role model routing
NIM_PRIMARY_MODEL  : str        = os.getenv(
    "NIM_PRIMARY_MODEL",  "deepseek-ai/deepseek-v3.2"
)
NIM_FALLBACK_MODEL : str        = os.getenv(
    "NIM_FALLBACK_MODEL", "deepseek-ai/deepseek-v3.1"
)

# ---------------------------------------------------------------------------
# OpenRouter settings  (Phase 4 fallback)
# ---------------------------------------------------------------------------

OPENROUTER_API_KEY : str | None = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL   : str        = os.getenv(
    "OPENROUTER_MODEL", "deepseek/deepseek-chat"
)
OPENROUTER_REFERER : str        = os.getenv("OPENROUTER_REFERER", "")
OPENROUTER_TITLE   : str        = os.getenv("OPENROUTER_TITLE",   "NotiFlow")

# ---------------------------------------------------------------------------
# Gemini settings  (fallback)
# ---------------------------------------------------------------------------

GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

# ---------------------------------------------------------------------------
# Excel sync path
# ---------------------------------------------------------------------------

_env_excel      = os.getenv("EXCEL_FILE_PATH")
EXCEL_SYNC_FILE = Path(_env_excel) if _env_excel else DATA_FILE

# ---------------------------------------------------------------------------
# Google Sheets settings
# ---------------------------------------------------------------------------

GOOGLE_SHEETS_CREDENTIALS: str = os.getenv(
    "GOOGLE_SHEETS_CREDENTIALS", "credentials/sheets.json"
)
GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")

# ---------------------------------------------------------------------------
# Ensure data directory exists at import time
# ---------------------------------------------------------------------------

DATA_DIR.mkdir(parents=True, exist_ok=True)
