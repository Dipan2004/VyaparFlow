"""
agent/extraction_agent.py
-------------------------
Compatibility shim + legacy functional API for NotiFlow Autonomous.

Old callers using:
    from agent.extraction_agent import extract_fields

…continue to work unchanged.

New code should use:
    from app.agents.extraction_agent import ExtractionAgent
    ctx = ExtractionAgent().run(context)
"""
from __future__ import annotations

from app.agents.extraction_agent import ExtractionAgent  # noqa: F401 — re-export

VALID_INTENTS = {"order", "payment", "credit", "return", "preparation", "other"}


def extract_fields(message: str, intent: str) -> dict:
    """
    Legacy functional wrapper around ExtractionAgent.

    Returns:
        Dict with "intent" + extracted fields. Missing fields are null.
    """
    from app.core.context import create_context, update_context
    ctx = create_context(message)
    update_context(ctx, intent=intent)
    ctx = ExtractionAgent().run(ctx)
    result = dict(ctx.get("data", {}))
    result["intent"] = ctx.get("intent", intent)
    return result
