"""
app/agents/validation_agent.py
------------------------------
ValidationAgent - Stage 3 of the NotiFlow pipeline.

Wraps validators/data_validator.py into the BaseAgent interface.
Normalises numbers, text, and payment aliases in context["data"] and
context["multi_data"] so multi-intent routing receives validated payloads.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.base_agent import BaseAgent
from app.core.context import update_context

logger = logging.getLogger(__name__)


class ValidationAgent(BaseAgent):
    """Normalise and validate extracted business data."""

    name = "ValidationAgent"
    input_keys = ["intent", "intents", "data", "multi_data"]
    output_keys = ["data", "multi_data", "state"]
    action = "Normalise numbers, text, and payment aliases"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        intent = context.get("intent", "other")
        intents = context.get("intents") or [intent]
        raw = context.get("data", {})
        multi_raw = context.get("multi_data", {}) or {}

        try:
            from app.validators.data_validator import validate_data

            validated_multi = {
                intent_name: validate_data(
                    intent_name,
                    multi_raw.get(intent_name, raw if intent_name == intent else {}),
                )
                for intent_name in intents
            }
            validated = validated_multi.get(intent, validate_data(intent, raw))
        except Exception as exc:
            logger.warning("[ValidationAgent] validation error (%s) - using raw data", exc)
            validated_multi = multi_raw or {intent: raw}
            validated = raw

        update_context(context, data=validated, multi_data=validated_multi, state="validated")
        logger.info("[ValidationAgent] validated data for intent '%s'", intent)
        return context
