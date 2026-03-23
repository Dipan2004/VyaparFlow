"""
services/notification_generator.py
-----------------------------------
Gemini-powered business notification generator for Notiflow.

Purpose: generate realistic Hinglish business notifications for demo
automation. This is entirely optional — the frontend simulation continues
to work independently.

Two modes:
  1. Live Gemini generation  — calls Gemini API (requires GEMINI_API_KEY)
  2. Static fallback pool    — returns from a hardcoded set when Gemini
                               is unavailable (safe for offline demos)

Public API
----------
get_notifications(n: int = 5) -> list[dict]
    Returns a list of notification dicts:
    [{"source": "whatsapp", "message": "..."}, ...]

stream_notifications(n, delay_seconds) -> AsyncGenerator
    Async generator yielding one notification at a time with a delay.
    Used by the WebSocket endpoint.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static fallback pool (used when Gemini is unavailable)
# ---------------------------------------------------------------------------

_FALLBACK_NOTIFICATIONS: list[dict] = [
    {"source": "whatsapp", "message": "bhaiya 3 kurti bhej dena"},
    {"source": "payment",  "message": "rahul ne 15000 bheja UPI se"},
    {"source": "whatsapp", "message": "size chota hai exchange karna hai"},
    {"source": "whatsapp", "message": "udhar me de dijiye"},
    {"source": "amazon",   "message": "priya ke liye 2 kilo aata bhej dena"},
    {"source": "payment",  "message": "amit bhai ka 8000 gpay se aaya"},
    {"source": "whatsapp", "message": "3 kurti ka set ready rakhna"},
    {"source": "return",   "message": "maal kharab tha wapas bhej diya"},
    {"source": "whatsapp", "message": "suresh ko 500 ka maal udhar dena"},
    {"source": "amazon",   "message": "order cancel karna hai, size bada hai"},
    {"source": "payment",  "message": "50 piece pack karke rakhna kal tak"},
    {"source": "whatsapp", "message": "geeta ke liye 5 metre kapda bhej dena"},
]


def _get_fallback(n: int) -> list[dict]:
    """Return n randomly sampled notifications from the static pool."""
    pool = _FALLBACK_NOTIFICATIONS * (n // len(_FALLBACK_NOTIFICATIONS) + 1)
    return random.sample(pool, min(n, len(pool)))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_notifications(n: int = 5) -> list[dict]:
    """
    Get n business notifications.

    Tries Gemini first; falls back to static pool silently if unavailable.

    Args:
        n: Number of notifications to generate/return.

    Returns:
        List of {"source": str, "message": str} dicts.
    """
    try:
        from app.services.gemini_client import generate_notifications
        results = generate_notifications(n)
        if results:
            return results
        logger.info("Gemini returned empty list — using fallback pool.")
    except Exception as exc:
        logger.info("Gemini unavailable (%s) — using fallback pool.", exc)

    return _get_fallback(n)


async def stream_notifications(
    n: int = 5,
    delay_seconds: float = 2.0,
) -> AsyncGenerator[dict, None]:
    """
    Async generator that yields one notification at a time.

    Fetches a fresh batch from get_notifications() then yields them
    one-by-one with a configurable delay between each.

    Args:
        n:             Number of notifications per batch.
        delay_seconds: Pause between yielded notifications.

    Yields:
        {"source": str, "message": str}
    """
    notifications = get_notifications(n)
    for notification in notifications:
        yield notification
        await asyncio.sleep(delay_seconds)