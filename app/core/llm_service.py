"""
app/core/llm_service.py
-----------------------
Unified LLM abstraction for NotiFlow Autonomous.

ALL LLM calls in the system go through this single service.
No other module is allowed to call an LLM API directly.

Primary backend : NVIDIA NIM API  (OpenAI-compatible endpoint)
Fallback backend: Google Gemini   (existing gemini_client.py)

Configuration (set in .env):
    NVIDIA_NIM_API_KEY    — required for live mode
    NVIDIA_NIM_BASE_URL   — default: https://integrate.api.nvidia.com/v1
    NVIDIA_NIM_MODEL      — default: meta/llama-3.1-8b-instruct

Public API
----------
LLMService().generate(prompt, max_tokens=256) -> str
    Returns raw text response.

get_llm() -> LLMService
    Module-level singleton accessor.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (read once at import)
# ---------------------------------------------------------------------------

_NIM_API_KEY  : Optional[str] = os.getenv("NVIDIA_NIM_API_KEY")
_NIM_BASE_URL : str           = os.getenv(
    "NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"
)
_NIM_MODEL    : str           = os.getenv(
    "NVIDIA_NIM_MODEL", "meta/llama-3.1-8b-instruct"
)


# ---------------------------------------------------------------------------
# LLMService
# ---------------------------------------------------------------------------

class LLMService:
    """
    Single entry point for all LLM inference in NotiFlow.

    Usage:
        from app.core.llm_service import get_llm
        response = get_llm().generate(prompt)
    """

    def generate(self, prompt: str, max_tokens: int = 256) -> str:
        """
        Send a prompt to the best available model and return the raw text.

        Tries NVIDIA NIM first; falls back to Gemini on any failure.

        Args:
            prompt:     Fully rendered prompt string.
            max_tokens: Maximum tokens to generate.

        Returns:
            Raw text response (may contain JSON — callers parse it).

        Raises:
            RuntimeError: If ALL backends fail.
        """
        nim_error: Optional[Exception] = None

        # ── Attempt NVIDIA NIM ───────────────────────────────────────────────
        try:
            result = self._call_nim(prompt, max_tokens)
            logger.info("LLMService → nim (success, model=%s)", _NIM_MODEL)
            return result
        except Exception as exc:
            nim_error = exc
            logger.warning("NIM unavailable (%s) — falling back to Gemini.", exc)

        # ── Fallback: Gemini ─────────────────────────────────────────────────
        try:
            result = self._call_gemini(prompt)
            logger.info("LLMService → gemini (fallback)")
            return result
        except Exception as gemini_exc:
            logger.error("Gemini fallback also failed: %s", gemini_exc)
            raise RuntimeError(
                f"All LLM backends are unavailable.\n"
                f"  NIM error:    {nim_error}\n"
                f"  Gemini error: {gemini_exc}"
            ) from gemini_exc

    # ── Private: NVIDIA NIM ──────────────────────────────────────────────────

    def _call_nim(self, prompt: str, max_tokens: int) -> str:
        """Call NVIDIA NIM via its OpenAI-compatible chat endpoint."""
        if not _NIM_API_KEY:
            raise RuntimeError(
                "NVIDIA_NIM_API_KEY is not set. "
                "Add it to your .env file: NVIDIA_NIM_API_KEY=your_key_here"
            )

        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError(
                "openai package is not installed. Run: pip install openai"
            )

        client = OpenAI(
            base_url=_NIM_BASE_URL,
            api_key=_NIM_API_KEY,
        )

        completion = client.chat.completions.create(
            model=_NIM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens,
        )

        text = completion.choices[0].message.content or ""
        logger.debug("NIM raw response: %r", text[:200])
        return text.strip()

    # ── Private: Gemini fallback ─────────────────────────────────────────────

    @staticmethod
    def _call_gemini(prompt: str) -> str:
        """Delegate to existing gemini_client for fallback."""
        # Import path works from both old layout and new layout
        try:
            from app.services.gemini_client import generate
        except ImportError:
            from app.services.gemini_client import generate
        return generate(prompt)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_instance: Optional[LLMService] = None


def get_llm() -> LLMService:
    """Return the shared LLMService singleton."""
    global _instance
    if _instance is None:
        _instance = LLMService()
    return _instance
