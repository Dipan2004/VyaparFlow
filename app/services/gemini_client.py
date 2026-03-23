"""
models/gemini_client.py
-----------------------
Gemini API client for Notiflow.

Serves two distinct roles:

  1. FALLBACK REASONER — used by ModelRouter when Nova is unavailable.
     generate(prompt) returns a plain-text response that must match
     Nova's JSON output schema exactly (enforced by the prompt).

  2. NOTIFICATION GENERATOR — used by notification_generator.py to
     produce realistic Hinglish business notifications for demo mode.
     generate_notifications(n) returns a list of notification dicts.

Configuration
-------------
  GEMINI_API_KEY — from .env / environment variable

Dependencies
------------
  pip install google-generativeai
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Gemini model to use — flash is fast and sufficient for this use case
_GEMINI_MODEL = "gemini-2.5-flash"

_client = None  # lazy singleton


def _get_client():
    """Return a cached Gemini GenerativeModel instance."""
    global _client
    if _client is not None:
        return _client

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. "
            "Add it to your .env file: GEMINI_API_KEY=your_key_here"
        )

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _client = genai.GenerativeModel(_GEMINI_MODEL)
        logger.info("Gemini client initialised (model=%s)", _GEMINI_MODEL)
        return _client
    except ImportError:
        raise RuntimeError(
            "google-generativeai is not installed. "
            "Run: pip install google-generativeai"
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to initialise Gemini client: {exc}") from exc


def _strip_fences(text: str) -> str:
    """Strip markdown code fences from model output."""
    return re.sub(r"```(?:json)?|```", "", text).strip()


# ---------------------------------------------------------------------------
# Public API — Role 1: Fallback reasoner for ModelRouter
# ---------------------------------------------------------------------------

def generate(prompt: str) -> str:
    """
    Send a prompt to Gemini and return the raw text response.

    Used by ModelRouter as a Nova fallback. The prompt already instructs
    the model to return JSON — this function returns the raw string and
    lets the caller parse it.

    Args:
        prompt: Fully rendered prompt (same prompt sent to Nova).

    Returns:
        Raw text response from Gemini (may contain JSON).

    Raises:
        RuntimeError: If the API call fails or client cannot be initialised.
    """
    client = _get_client()
    try:
        response = client.generate_content(prompt)
        raw = response.text or ""
        logger.debug("Gemini raw response: %r", raw[:200])
        return _strip_fences(raw)
    except Exception as exc:
        logger.error("Gemini generate() failed: %s", exc)
        raise RuntimeError(f"Gemini API error: {exc}") from exc


# ---------------------------------------------------------------------------
# Public API — Role 2: Notification generator
# ---------------------------------------------------------------------------

_NOTIFICATION_PROMPT = """
You are simulating incoming business notifications for a small business in India.

Generate {n} realistic business notifications in Hinglish (Hindi + English mix).

Each notification must come from one of these sources:
- whatsapp   (informal text from customers or suppliers)
- payment    (UPI payment confirmation message)
- amazon     (marketplace order or return notification)
- return     (customer return or exchange request)

Each notification must represent ONE of these business events:
- An order for a product (item name + quantity)
- A payment received (person name + amount)
- A credit/udhar request
- A return or exchange request
- A preparation/packing request

Rules:
- Use natural Hinglish phrasing. Not too formal.
- Vary sources and event types.
- Include real-sounding names (Rahul, Priya, Suresh, Amit, etc.)
- Include real product names (kurti, aata, daal, saree, etc.)
- Do NOT include any explanation or preamble.
- Return ONLY a valid JSON array, nothing else.

Output format (JSON array only, no markdown):
[
  {{"source": "whatsapp", "message": "bhaiya 3 kurti bhej dena"}},
  {{"source": "payment", "message": "Rahul ne 15000 bheja UPI se"}}
]
"""


def generate_notifications(n: int = 5) -> list[dict[str, str]]:
    """
    Generate n realistic Hinglish business notifications via Gemini.

    Args:
        n: Number of notifications to generate (default 5).

    Returns:
        List of dicts with keys "source" and "message".
        Returns an empty list if generation fails (non-fatal).

    Example:
        >>> generate_notifications(3)
        [
            {"source": "whatsapp", "message": "bhaiya 3 kurti bhej dena"},
            {"source": "payment",  "message": "Rahul ne 15000 bheja"},
            {"source": "return",   "message": "size chota hai exchange karna hai"},
        ]
    """
    prompt = _NOTIFICATION_PROMPT.format(n=n)
    try:
        raw  = generate(prompt)
        data = json.loads(raw)
        if not isinstance(data, list):
            logger.warning("Gemini notification response was not a list: %s", type(data))
            return []
        # Validate each entry has required keys
        valid = [
            item for item in data
            if isinstance(item, dict)
            and "source"  in item
            and "message" in item
        ]
        logger.info("Generated %d notifications via Gemini", len(valid))
        return valid
    except json.JSONDecodeError as exc:
        logger.warning("Could not parse Gemini notification output as JSON: %s", exc)
        return []
    except Exception as exc:
        logger.warning("generate_notifications failed: %s", exc)
        return []