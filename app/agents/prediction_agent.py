"""
app/agents/prediction_agent.py
-------------------------------
PredictionAgent — Autonomy Layer, Step 3.

Pure rule-based risk scoring. No ML, no external calls.

Rules evaluated (each contributes a score 0–1):
    1. High amount (payment/credit > 10000)       → risk +0.4
    2. Very high amount (> 50000)                 → risk +0.3 additional
    3. Null customer on payment/credit            → risk +0.3
    4. Repeated errors in context                 → risk +0.2 per error (max 0.4)
    5. Verification failed/partial                → risk +0.3
    6. Pipeline ended in partial/failed state     → risk +0.2
    7. Return with no reason                      → risk +0.2
    8. Credit with no amount                      → risk +0.2

Final risk level:
    score < 0.3  → "low"
    score < 0.6  → "medium"
    score >= 0.6 → "high"

Output written to context["risk"]:
    {
        "level":   "low" | "medium" | "high",
        "score":   float,          # 0.0–1.0
        "reasons": list[str],      # which rules fired
        "action":  str,            # recommended action
    }
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)

_HIGH_AMOUNT      = 10_000
_VERY_HIGH_AMOUNT = 50_000

_ACTIONS = {
    "low":    "Continue normal processing",
    "medium": "Flag for manual review",
    "high":   "Escalate immediately and pause processing",
}


class PredictionAgent(BaseAgent):
    """Rule-based risk scorer — no ML, fully deterministic."""

    name        = "PredictionAgent"
    input_keys  = ["intent", "data", "verification", "errors", "state"]
    output_keys = ["risk"]
    action      = "Score transaction risk using rule-based evaluation"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        intent       = (context.get("intent") or "other").lower()
        data         = context.get("data", {})
        verification = context.get("verification", {})
        errors       = context.get("errors", [])
        state        = context.get("state", "")

        score   = 0.0
        reasons: list[str] = []

        # ── Rule 1 & 2: high-value transaction ───────────────────────────────
        amount = data.get("amount")
        if amount is not None and intent in ("payment", "credit"):
            try:
                amount_f = float(amount)
                if amount_f > _VERY_HIGH_AMOUNT:
                    score += 0.7
                    reasons.append(
                        f"Very high amount ₹{amount_f:,.0f} (>{_VERY_HIGH_AMOUNT:,})"
                    )
                elif amount_f > _HIGH_AMOUNT:
                    score += 0.4
                    reasons.append(
                        f"High amount ₹{amount_f:,.0f} (>{_HIGH_AMOUNT:,})"
                    )
            except (ValueError, TypeError):
                pass

        # ── Rule 3: null customer on financial intent ────────────────────────
        if intent in ("payment", "credit") and not data.get("customer"):
            score += 0.3
            reasons.append("Customer is unknown on a financial transaction")

        # ── Rule 4: repeated errors ──────────────────────────────────────────
        error_count = len(errors)
        if error_count > 0:
            error_score = min(0.4, error_count * 0.2)
            score += error_score
            reasons.append(f"{error_count} error(s) accumulated in pipeline")

        # ── Rule 5: verification failed ──────────────────────────────────────
        v_status = verification.get("status", "")
        if v_status == "fail":
            score += 0.3
            reasons.append("Verification failed for this transaction")
        elif v_status == "partial":
            score += 0.15
            reasons.append("Verification only partially passed")

        # ── Rule 6: abnormal pipeline state ──────────────────────────────────
        if state in ("failed", "partial"):
            score += 0.2
            reasons.append(f"Pipeline ended in '{state}' state")

        # ── Rule 7: return with no reason ────────────────────────────────────
        if intent == "return" and not data.get("reason"):
            score += 0.2
            reasons.append("Return request has no stated reason")

        # ── Rule 8: credit with no amount ────────────────────────────────────
        if intent == "credit" and data.get("amount") is None:
            score += 0.2
            reasons.append("Credit extended with no amount specified")

        # ── Clamp and classify ───────────────────────────────────────────────
        score = min(round(score, 2), 1.0)
        if score < 0.3:
            level = "low"
        elif score < 0.6:
            level = "medium"
        else:
            level = "high"

        risk = {
            "level":   level,
            "score":   score,
            "reasons": reasons,
            "action":  _ACTIONS[level],
        }

        context["risk"] = risk
        logger.info(
            "[PredictionAgent] risk=%s score=%.2f reasons=%d",
            level, score, len(reasons)
        )

        # ── Also contribute to the shared priority score ──────────────────────
        # High risk contributes 35 pts, medium 15 pts — UrgencyAgent will
        # combine these with keyword/amount signals to derive the final label.
        from app.core.priority import contribute_priority_score
        if level == "high":
            contribute_priority_score(context, 35, f"Risk level is high (score={score})")
        elif level == "medium":
            contribute_priority_score(context, 15, f"Risk level is medium (score={score})")

        return context