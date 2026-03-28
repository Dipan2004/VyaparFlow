"""
app/agents/skill_router_agent.py
--------------------------------
SkillRouterAgent - Stage 4 of the NotiFlow pipeline.

Wraps app/services/router.py into the BaseAgent interface.
Dispatches to the correct business skill for every detected intent while
keeping context["event"] backward compatible as the primary intent result.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.base_agent import BaseAgent
from app.core.context import update_context

logger = logging.getLogger(__name__)


class SkillRouterAgent(BaseAgent):
    """Route the validated context to the appropriate business skill(s)."""

    name = "SkillRouterAgent"
    input_keys = ["intent", "intents", "data", "multi_data"]
    output_keys = ["event", "invoice", "payment", "state"]
    action = "Dispatch validated data to business skills"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        try:
            from app.services.router import route_to_skill
        except ImportError:
            from app.services.router import route_to_skill  # type: ignore

        primary_intent = context.get("intent", "other")
        intents = context.get("intents") or [primary_intent]
        multi_data = context.get("multi_data", {}) or {}

        primary_event: dict[str, Any] | None = None

        for intent_name in intents:
            payload = multi_data.get(intent_name)
            if payload is None:
                payload = context.get("data", {}) if intent_name == primary_intent else {}

            event = route_to_skill(intent_name, payload, context=context)

            if intent_name == primary_intent or primary_event is None:
                primary_event = event

            if event.get("payment") and not context.get("payment"):
                update_context(context, payment=event.get("payment"))
            if event.get("invoice") and not context.get("invoice"):
                update_context(context, invoice=event.get("invoice"))

        update_context(
            context,
            event=primary_event or {"event": "unhandled", "intent": primary_intent, "data": context.get("data", {})},
            invoice=context.get("invoice"),
            payment=context.get("payment"),
            state="routed",
        )
        logger.info("[SkillRouterAgent] primary_event=%s intents=%s", context.get("event", {}).get("event"), intents)
        return context
