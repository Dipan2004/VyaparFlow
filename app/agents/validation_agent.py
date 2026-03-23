"""
app/agents/validation_agent.py
------------------------------
ValidationAgent — Stage 3 of the NotiFlow pipeline.

Wraps validators/data_validator.py into the BaseAgent interface.
Normalises numbers, text, and payment aliases in context["data"].
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.base_agent import BaseAgent
from app.core.context import update_context

logger = logging.getLogger(__name__)


class ValidationAgent(BaseAgent):
    """Normalise and validate extracted business data."""

    name        = "ValidationAgent"
    input_keys  = ["intent", "data"]
    output_keys = ["data", "state"]
    action      = "Normalise numbers, text, and payment aliases"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Validate context["data"] in-place and transition state to "validated".

        Reads context["intent"] and context["data"].
        Writes cleaned data back to context["data"].
        """
        intent = context.get("intent", "other")
        raw    = context.get("data", {})

        try:
            # Import path works regardless of old vs new layout
            try:
                from app.validators.data_validator import validate_data
            except ImportError:
                from app.validators.data_validator import validate_data

            validated = validate_data(intent, raw)
        except Exception as exc:
            logger.warning("[ValidationAgent] validation error (%s) — using raw data", exc)
            validated = raw

        update_context(context, data=validated, state="validated")
        logger.info("[ValidationAgent] validated data for intent '%s'", intent)
        return context
