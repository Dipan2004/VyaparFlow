"""
app/agents/extraction_agent.py
------------------------------
ExtractionAgent — Stage 2 of the NotiFlow pipeline.

Wraps the existing entity extraction logic into the BaseAgent interface.
Reads context["intent"], extracts structured fields, writes context["data"].

NO business logic is changed — this is a thin wrap over the same
prompt + schema + parsing logic from agent/extraction_agent.py.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.core.base_agent import BaseAgent
from app.core.context import update_context
from app.core.llm_service import get_llm

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "extraction_prompt.txt"

INTENT_SCHEMA: dict[str, list[str]] = {
    "order":       ["customer", "item", "quantity"],
    "payment":     ["customer", "amount", "payment_type"],
    "credit":      ["customer", "item", "quantity", "amount"],
    "return":      ["customer", "item", "reason"],
    "preparation": ["item", "quantity"],
    "other":       ["note"],
}
VALID_INTENTS = set(INTENT_SCHEMA.keys())


class ExtractionAgent(BaseAgent):
    """Extract structured business fields from a Hinglish message."""

    name        = "ExtractionAgent"
    input_keys  = ["message", "intent"]
    output_keys = ["data", "state"]
    action      = "Extract structured entities from message"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Extract fields and write them into context["data"].

        Reads context["message"] and context["intent"].
        Writes context["data"] and transitions state to "extracted".
        """
        message = context.get("message", "").strip()
        intent  = (context.get("intent") or "other").lower().strip()

        if not message:
            update_context(context, data=self._null_data(intent), state="extracted")
            return context

        if intent not in VALID_INTENTS:
            intent = "other"

        prompt = self._load_prompt(message, intent)
        raw    = get_llm().generate(prompt, max_tokens=256)
        data   = self._parse(raw, intent)

        update_context(context, data=data, state="extracted")
        logger.info("[ExtractionAgent] extracted=%s", data)
        return context

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _load_prompt(message: str, intent: str) -> str:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
        prompt   = template.replace("{message}", message.strip())
        prompt   = prompt.replace("{intent}",  intent.strip().lower())
        return prompt

    @staticmethod
    def _parse(raw: str, intent: str) -> dict:
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            match  = re.search(r"\{.*\}", cleaned, re.DOTALL)
            parsed = {}
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    logger.warning("[ExtractionAgent] could not parse JSON; using nulls")

        schema = INTENT_SCHEMA.get(intent, INTENT_SCHEMA["other"])
        result = {field: parsed.get(field) for field in schema}

        # Normalise customer to Title Case
        if "customer" in result and isinstance(result["customer"], str):
            result["customer"] = result["customer"].strip().title()

        # Coerce numeric fields
        for num_field in ("amount", "quantity"):
            if num_field in result and result[num_field] is not None:
                try:
                    val = float(result[num_field])
                    result[num_field] = int(val) if val.is_integer() else val
                except (ValueError, TypeError):
                    result[num_field] = None

        return result

    @staticmethod
    def _null_data(intent: str) -> dict:
        schema = INTENT_SCHEMA.get(intent, INTENT_SCHEMA["other"])
        return {field: None for field in schema}
