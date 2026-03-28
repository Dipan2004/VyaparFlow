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
            logger.error("[IntentAgent] all LLM backends failed - using heuristic fallback: %s", exc)
            # Heuristic fallback: detect intent from message keywords
            intents = self._heuristic_intent(message)
            update_context(context, intent=intents[0], intents=intents, state="intent_detected")
            logger.info("[IntentAgent] heuristic intents=%s (primary=%s)", intents, intents[0])
            return context
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

    @staticmethod
    def _heuristic_intent(message: str) -> list[str]:
        """
        Heuristic fallback: detect intent from message keywords when LLM fails.
        """
        msg = message.lower()
        intents = []

        # Order keywords - check FIRST to prioritize (more specific)
        if any(kw in msg for kw in ['bhej dena', 'bhejna', 'chahiye', 'want', 'dena', 'karna', '3 kurti', '2 shirt', '4 pant']):
            intents.append('order')

        # Payment keywords
        if any(kw in msg for kw in ['payment', 'paid', 'bheja', 'transfer', 'upi', 'gpay', 'pay', 'kiya']):
            intents.append('payment')

        # Return keywords
        if any(kw in msg for kw in ['return', 'wapas', 'revert', 'cancel', 'refund']):
            intents.append('return')

        # Credit keywords
        if any(kw in msg for kw in ['credit', 'liye', 'len', 'due', 'baaki']):
            intents.append('credit')

        # Preparation keywords
        if any(kw in msg for kw in ['prepare', 'ready', 'pack', 'taiyar']):
            intents.append('preparation')

        # Preparation keywords
        if any(kw in msg for kw in ['prepare', 'ready', 'pack', 'taiyar']):
            intents.append('preparation')

        return intents if intents else ['other']
