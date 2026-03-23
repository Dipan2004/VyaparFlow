"""
app/agents/urgency_agent.py
----------------------------
UrgencyAgent — Autonomy Layer, Step 4.

Detects urgency signals in the message and data, then sets
context["priority"] to "low" | "normal" | "high" | "critical".

Rules (first match wins, highest priority):
    "critical" — message contains crisis keywords OR amount > 100000
    "high"     — message contains urgency keywords OR amount > 50000
                 OR risk level is "high"
    "normal"   — default for most transactions
    "low"      — message is informational / intent is "other"

Urgency keywords (Hinglish-aware):
    crisis:  "emergency", "crisis", "block", "fraud", "chori", "problem"
    urgent:  "jaldi", "urgent", "asap", "abhi", "turant", "important",
             "zaruri", "help", "please", "kal tak"
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)

_CRISIS_KEYWORDS  = {"emergency", "crisis", "block", "fraud", "chori", "problem"}
_URGENT_KEYWORDS  = {
    "jaldi", "urgent", "asap", "abhi", "turant", "important",
    "zaruri", "help", "please", "kal tak", "immediately", "now",
}
_CRITICAL_AMOUNT  = 100_000
_HIGH_AMOUNT      = 50_000


class UrgencyAgent(BaseAgent):
    """Detect urgency signals and set context priority."""

    name        = "UrgencyAgent"
    input_keys  = ["message", "data", "intent", "risk"]
    output_keys = ["priority"]
    action      = "Detect urgency signals and set request priority"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        message = (context.get("message") or "").lower()
        data    = context.get("data", {})
        intent  = (context.get("intent") or "other").lower()
        risk    = context.get("risk", {})

        words         = set(message.split())
        amount        = self._safe_amount(data.get("amount"))
        risk_level    = risk.get("level", "low")

        # ── Evaluate rules top-down ──────────────────────────────────────────
        if (words & _CRISIS_KEYWORDS) or (amount is not None and amount > _CRITICAL_AMOUNT):
            priority = "critical"
            reason   = (
                f"Crisis keyword detected" if words & _CRISIS_KEYWORDS
                else f"Amount ₹{amount:,.0f} exceeds critical threshold"
            )

        elif (
            (words & _URGENT_KEYWORDS)
            or (amount is not None and amount > _HIGH_AMOUNT)
            or risk_level == "high"
        ):
            priority = "high"
            if words & _URGENT_KEYWORDS:
                matched = words & _URGENT_KEYWORDS
                reason  = f"Urgency keyword(s) detected: {', '.join(matched)}"
            elif amount is not None and amount > _HIGH_AMOUNT:
                reason  = f"Amount ₹{amount:,.0f} exceeds high threshold"
            else:
                reason  = "Risk level is high"

        elif intent == "other":
            priority = "low"
            reason   = "Intent is 'other' — informational message"

        else:
            priority = "normal"
            reason   = "No urgency signals detected"

        context["priority"] = priority
        context.setdefault("metadata", {})["urgency_reason"] = reason

        logger.info("[UrgencyAgent] priority=%s — %s", priority, reason)
        return context

    @staticmethod
    def _safe_amount(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None