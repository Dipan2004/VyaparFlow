"""
app/agents/urgency_agent.py
----------------------------
UrgencyAgent — Autonomy Layer, Step 4.

Detects urgency signals and contributes to context["priority_score"].
After accumulating all signals it calls derive_priority_label() which
derives the final context["priority"] string from the score.

Score contributions:
    Crisis keyword OR amount > 100k  → +80 points
    Urgency keyword                  → +50 points
    Amount > 50k                     → +45 points
    Risk level == "high"             → +35 points
    Intent == "other"                → –10 (score stays 0 if nothing else)

Final label derived by derive_priority_label():
    score > 70  → "high"
    score > 40  → "medium"
    score ≤ 40  → "low"
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.base_agent import BaseAgent
from app.core.priority   import contribute_priority_score, derive_priority_label

logger = logging.getLogger(__name__)

_CRISIS_KEYWORDS = {"emergency", "crisis", "block", "fraud", "chori", "problem"}
_URGENT_KEYWORDS = {
    "jaldi", "urgent", "asap", "abhi", "turant", "important",
    "zaruri", "help", "please", "kal tak", "immediately", "now",
}
_CRITICAL_AMOUNT = 100_000
_HIGH_AMOUNT     = 50_000


class UrgencyAgent(BaseAgent):
    """Detect urgency signals, accumulate priority score, derive final label."""

    name        = "UrgencyAgent"
    input_keys  = ["message", "data", "intent", "risk", "priority_score"]
    output_keys = ["priority_score", "priority"]
    action      = "Accumulate urgency signals into priority score and derive label"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        message    = (context.get("message") or "").lower()
        data       = context.get("data", {})
        intent     = (context.get("intent") or "other").lower()
        risk       = context.get("risk", {})
        words      = set(message.split())
        amount     = self._safe_amount(data.get("amount"))
        risk_level = risk.get("level", "low")

        # ── Contribute scores for each signal ────────────────────────────────
        if words & _CRISIS_KEYWORDS:
            matched = words & _CRISIS_KEYWORDS
            contribute_priority_score(
                context, 80,
                f"Crisis keyword(s) detected: {', '.join(matched)}"
            )

        if amount is not None and amount > _CRITICAL_AMOUNT:
            contribute_priority_score(
                context, 80,
                f"Amount ₹{amount:,.0f} exceeds critical threshold ({_CRITICAL_AMOUNT:,})"
            )

        if words & _URGENT_KEYWORDS:
            matched = words & _URGENT_KEYWORDS
            contribute_priority_score(
                context, 50,
                f"Urgency keyword(s): {', '.join(matched)}"
            )

        if amount is not None and _HIGH_AMOUNT < amount <= _CRITICAL_AMOUNT:
            contribute_priority_score(
                context, 45,
                f"Amount ₹{amount:,.0f} exceeds high threshold ({_HIGH_AMOUNT:,})"
            )

        if risk_level == "high":
            contribute_priority_score(context, 35, "Risk level is high")

        # Store urgency reason for escalation agent to read
        score = context.get("priority_score", 0)
        context.setdefault("metadata", {})["urgency_reason"] = (
            f"priority_score={score}"
        )

        # ── Derive final label from accumulated score ─────────────────────────
        label = derive_priority_label(context)
        logger.info(
            "[UrgencyAgent] score=%d → priority=%s", score, label
        )
        return context

    @staticmethod
    def _safe_amount(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None