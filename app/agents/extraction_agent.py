"""
app/agents/extraction_agent.py
------------------------------
ExtractionAgent — Stage 2 of the NotiFlow pipeline.

Phase 5: Multi-intent support.
    - Reads context["intents"] (list); falls back to context["intent"]
    - Single LLM call extracts data for ALL intents at once
    - Writes context["multi_data"]  = {intent: {fields}}  (all intents)
    - Writes context["data"]        = multi_data[primary]  (backward compat)

Single-intent path is identical to Phase 1-4 behaviour.
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
    """Extract structured business fields for ALL detected intents."""

    name        = "ExtractionAgent"
    input_keys  = ["message", "intent", "intents"]
    output_keys = ["data", "multi_data", "state"]
    action      = "Extract structured entities for all detected intents"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        message = context.get("message", "").strip()

        # Resolve intents — Phase 5 uses context["intents"], fallback to ["intent"]
        intents = context.get("intents") or []
        if not intents:
            primary = (context.get("intent") or "other").lower().strip()
            intents = [primary]

        # Validate each intent
        intents = [i if i in VALID_INTENTS else "other" for i in intents]
        primary = intents[0]

        if not message:
            multi_data = {i: self._null_data(i) for i in intents}
            update_context(context,
                           data=multi_data[primary],
                           multi_data=multi_data,
                           state="extracted")
            return context

        # ── Single LLM call for all intents ──────────────────────────────
        prompt   = self._load_prompt(message, intents)
        raw      = get_llm().generate(
            prompt,
            max_tokens = 400,
            agent_name = self.name,
            task_type  = "extraction",
            context    = context,
        )
        multi_data = self._parse(raw, intents)

        update_context(context,
                       data=multi_data[primary],   # backward compat
                       multi_data=multi_data,
                       state="extracted")
        logger.info("[ExtractionAgent] intents=%s extracted=%s", intents, multi_data)
        return context

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _load_prompt(message: str, intents: list[str]) -> str:
        template   = _PROMPT_PATH.read_text(encoding="utf-8")
        intents_str = ", ".join(intents)
        prompt     = template.replace("{message}", message.strip())
        prompt     = prompt.replace("{intents}", intents_str)
        # Legacy placeholder — extraction_prompt.txt used to have {intent}
        prompt     = prompt.replace("{intent}",  intents_str)
        return prompt

    @staticmethod
    def _parse(raw: str, intents: list[str]) -> dict[str, dict]:
        """
        Parse LLM output into a per-intent data dict.

        Handles two response shapes:
          Single:  {"customer": "Rahul", "amount": 500, ...}
          Multi:   {"payment": {"customer": ...}, "order": {"item": ...}}

        Returns: {intent: {fields}} for every intent in intents.
        """
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        parsed: dict = {}
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    logger.warning("[ExtractionAgent] could not parse JSON; using nulls")

        multi_data: dict[str, dict] = {}

        if len(intents) == 1:
            # Single-intent response — flat dict
            intent = intents[0]
            multi_data[intent] = ExtractionAgent._extract_single(parsed, intent)
        else:
            # Multi-intent response — keyed by intent name
            for intent in intents:
                if intent in parsed and isinstance(parsed[intent], dict):
                    multi_data[intent] = ExtractionAgent._extract_single(
                        parsed[intent], intent
                    )
                else:
                    # Fallback: maybe LLM returned flat dict for first intent
                    if not multi_data and intent == intents[0]:
                        multi_data[intent] = ExtractionAgent._extract_single(parsed, intent)
                    else:
                        multi_data[intent] = ExtractionAgent._null_data(intent)

        # Guarantee every requested intent has an entry
        for intent in intents:
            if intent not in multi_data:
                multi_data[intent] = ExtractionAgent._null_data(intent)

        return multi_data

    @staticmethod
    def _extract_single(src: dict, intent: str) -> dict:
        """Build a schema-validated dict for one intent from a source dict."""
        schema = INTENT_SCHEMA.get(intent, INTENT_SCHEMA["other"])
        result = {field: src.get(field) for field in schema}

        # Normalise customer to Title Case
        if "customer" in result and isinstance(result["customer"], str):
            result["customer"] = result["customer"].strip().title()
            if result["customer"].lower() in ("null", "none", ""):
                result["customer"] = None

        # Coerce numeric fields
        for num_field in ("amount", "quantity"):
            if num_field in result and result[num_field] is not None:
                try:
                    val = float(result[num_field])
                    result[num_field] = int(val) if val == int(val) else val
                except (ValueError, TypeError):
                    result[num_field] = None

        return result

    @staticmethod
    def _null_data(intent: str) -> dict:
        schema = INTENT_SCHEMA.get(intent, INTENT_SCHEMA["other"])
        return {field: None for field in schema}