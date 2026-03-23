"""
app/agents/skill_router_agent.py
--------------------------------
SkillRouterAgent — Stage 4 of the NotiFlow pipeline.

Wraps agent/router.py into the BaseAgent interface.
Dispatches to the correct business skill based on context["intent"]
and writes the skill result to context["event"].
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.base_agent import BaseAgent
from app.core.context import update_context

logger = logging.getLogger(__name__)


class SkillRouterAgent(BaseAgent):
    """Route the validated context to the appropriate business skill."""

    name        = "SkillRouterAgent"
    input_keys  = ["intent", "data"]
    output_keys = ["event", "state"]
    action      = "Dispatch to business skill and execute"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Dispatch to the correct skill and write result to context["event"].

        Reads context["intent"] and context["data"].
        Writes context["event"] and transitions state to "routed".
        """
        intent = context.get("intent", "other")
        data   = context.get("data", {})

        try:
            from app.services.router import route_to_skill
        except ImportError:
            from app.services.router import route_to_skill  # type: ignore

        event = route_to_skill(intent, data)
        update_context(context, event=event, state="routed")
        logger.info("[SkillRouterAgent] event=%s", event.get("event"))
        return context
