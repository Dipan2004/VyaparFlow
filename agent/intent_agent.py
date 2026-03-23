"""
agent/intent_agent.py
---------------------
Compatibility shim + legacy functional API for NotiFlow Autonomous.

Old callers using:
    from agent.intent_agent import detect_intent

…continue to work unchanged. The function is a thin wrapper that
creates a temporary context, runs IntentAgent, and returns the old
{"intent": str} dict shape.

New code should use:
    from app.agents.intent_agent import IntentAgent
    ctx = IntentAgent().run(context)
"""
from __future__ import annotations

from app.agents.intent_agent import IntentAgent  # noqa: F401 — re-export


def detect_intent(message: str) -> dict:
    """
    Legacy functional wrapper around IntentAgent.

    Returns:
        {"intent": "<intent_string>"}
    """
    from app.core.context import create_context
    ctx = create_context(message)
    ctx = IntentAgent().run(ctx)
    return {"intent": ctx.get("intent", "other")}
