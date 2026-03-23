"""
app/agents/intent_agent.py
--------------------------
IntentAgent — Stage 1 of the NotiFlow pipeline.

Wraps the existing intent detection logic into the BaseAgent interface.
All Hinglish → intent classification happens here.

The agent:
    1. Loads the intent prompt template
    2. Calls LLMService (NIM → Gemini fallback)
    3. Parses the JSON response
    4. Writes context["intent"] and transitions state

NO business logic is changed — this is a thin wrap over the
same prompt + parsing logic that existed in agent/intent_agent.py.
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

# Prompt lives in the repo-level prompts/ folder (unchanged location)
_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "intent_prompt.txt"

VALID_INTENTS = {"order", "payment", "credit", "return", "preparation", "other"}


class IntentAgent(BaseAgent):
    """Classify the business intent of a Hinglish message."""

    name        = "IntentAgent"
    input_keys  = ["message"]
    output_keys = ["intent", "state"]
    action      = "Classify business intent from Hinglish message"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Detect intent and write it into context["intent"].

        Reads context["message"], writes context["intent"].
        Transitions state to "intent_detected" on success.
        """
        message = context.get("message", "").strip()
        if not message:
            logger.warning("[IntentAgent] empty message — defaulting to 'other'")
            update_context(context, intent="other", state="intent_detected")
            return context

        prompt = self._load_prompt(message)
        raw    = get_llm().generate(prompt, max_tokens=64)
        intent = self._parse(raw)

        update_context(context, intent=intent, state="intent_detected")
        logger.info("[IntentAgent] intent=%s", intent)
        return context

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _load_prompt(message: str) -> str:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
        return template.replace("{message}", message)

    @staticmethod
    def _parse(raw: str) -> str:
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        try:
            result = json.loads(cleaned)
            intent = result.get("intent", "other").lower().strip()
        except json.JSONDecodeError:
            match  = re.search(r'"intent"\s*:\s*"(\w+)"', cleaned)
            intent = match.group(1).lower() if match else "other"

        if intent not in VALID_INTENTS:
            logger.warning("[IntentAgent] unknown intent '%s' → 'other'", intent)
            intent = "other"
        return intent
