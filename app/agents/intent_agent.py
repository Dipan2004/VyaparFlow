"""
app/agents/intent_agent.py
--------------------------
IntentAgent — Stage 1 of the NotiFlow pipeline.

Phase 5: Multi-intent support.
    - Prompt now returns {"intents": ["payment", "order"]}
    - context["intents"] = full detected list
    - context["intent"]  = intents[0]  ← backward compat

Backward compat: if LLM returns old {"intent": "x"} format, wraps in list.
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

# Prompt lives in the repo-level prompts/ folder
_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "intent_prompt.txt"

VALID_INTENTS = {"order", "payment", "credit", "return", "preparation", "other"}


class IntentAgent(BaseAgent):
    """Classify ALL business intents from a Hinglish message."""

    name        = "IntentAgent"
    input_keys  = ["message"]
    output_keys = ["intent", "intents", "state"]
    action      = "Classify all business intents from Hinglish message"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Detect intents and write them into context.

        Writes:
            context["intents"] — ordered list of all detected intents
            context["intent"]  — primary intent (intents[0]) for backward compat
        Transitions state to "intent_detected" on success.
        """
        message = context.get("message", "").strip()
        if not message:
            logger.warning("[IntentAgent] empty message — defaulting to 'other'")
            update_context(context, intent="other", intents=["other"], state="intent_detected")
            return context

        prompt  = self._load_prompt(message)
        try:
            raw = get_llm().generate(
                prompt,
                max_tokens=96,
                agent_name=self.name,
                task_type="classification",
                context=context,
            )
        except Exception as exc:
            logger.error("[IntentAgent] all LLM backends failed - defaulting to 'other': %s", exc)
            raw = '{"intent": "other"}'
        intents = self._parse(raw)
        primary = intents[0]

        update_context(context, intent=primary, intents=intents, state="intent_detected")
        logger.info("[IntentAgent] intents=%s (primary=%s)", intents, primary)
        return context

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _load_prompt(message: str) -> str:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
        return template.replace("{message}", message)

    @staticmethod
    def _parse(raw: str) -> list[str]:
        """
        Parse LLM output into a list of valid intents.

        Handles:
          - New format:  {"intents": ["payment", "order"]}
          - Old format:  {"intent": "payment"}     ← backward compat
          - Bare string: payment
        Returns at least ["other"] on any parse failure.
        """
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        intents: list[str] = []

        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                if "intents" in result:
                    raw_list = result["intents"]
                    if isinstance(raw_list, list):
                        intents = [str(x).lower().strip() for x in raw_list]
                    else:
                        intents = [str(raw_list).lower().strip()]
                elif "intent" in result:
                    # Old single-intent format — wrap in list
                    intents = [str(result["intent"]).lower().strip()]
        except json.JSONDecodeError:
            # Try regex fallback for intents array (handles truncated/malformed JSON)
            arr_match = re.search(r'"intents"\s*:\s*\[([^\]]*)', cleaned)
            if arr_match:
                raw_items = arr_match.group(1)
                intents = [
                    m.lower().strip()
                    for m in re.findall(r'"(\w+)"', raw_items)
                ]
            else:
                # Try old single-intent regex
                match = re.search(r'"intent"\s*:\s*"(\w+)"', cleaned)
                if match:
                    intents = [match.group(1).lower()]

        # Validate — keep only known intents, deduplicate, preserve order
        seen:  set[str] = set()
        valid: list[str] = []
        for intent in intents:
            if intent in VALID_INTENTS and intent not in seen:
                valid.append(intent)
                seen.add(intent)

        if not valid:
            logger.warning("[IntentAgent] could not parse valid intents from: %r", raw[:80])
            valid = ["other"]

        return valid
