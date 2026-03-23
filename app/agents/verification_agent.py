"""
app/agents/verification_agent.py
---------------------------------
VerificationAgent — Autonomy Layer, Step 1.

Validates that the skill execution produced the expected output.
Reads context["intent"] and context["event"], writes context["verification"].

Output shape written to context["verification"]:
    {
        "status":     "ok" | "fail" | "partial",
        "confidence": 0.0 – 1.0,
        "checks":     list[str],   # human-readable check results
        "reason":     str,         # summary
    }

Never raises — failures are recorded as verification["status"] = "fail".
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Expected event name per intent
_EXPECTED_EVENTS: dict[str, str] = {
    "order":       "order_received",
    "payment":     "payment_recorded",
    "credit":      "credit_recorded",
    "return":      "return_requested",
    "preparation": "preparation_queued",
}

# Required fields inside event sub-dict per intent
_REQUIRED_FIELDS: dict[str, dict[str, list[str]]] = {
    "order":       {"order":   ["order_id", "item", "status"]},
    "payment":     {"payment": ["customer", "amount", "status"]},
    "credit":      {"credit":  ["customer", "status"]},
    "return":      {"return":  ["return_id", "status"]},
    "preparation": {"preparation": ["prep_id", "status"]},
}


class VerificationAgent(BaseAgent):
    """Validate that the pipeline produced a complete, expected result."""

    name        = "VerificationAgent"
    input_keys  = ["intent", "event", "data"]
    output_keys = ["verification"]
    action      = "Verify skill execution produced expected output"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        intent = (context.get("intent") or "other").lower()
        event  = context.get("event", {})
        checks: list[str] = []
        passed = 0
        total  = 0

        # ── Check 1: event exists ────────────────────────────────────────────
        total += 1
        if event:
            checks.append("✓ event dict is non-empty")
            passed += 1
        else:
            checks.append("✗ event dict is empty")

        # ── Check 2: correct event name ──────────────────────────────────────
        expected_event = _EXPECTED_EVENTS.get(intent)
        if expected_event:
            total += 1
            actual_event = event.get("event", "")
            if actual_event == expected_event:
                checks.append(f"✓ event name '{actual_event}' matches expected")
                passed += 1
            else:
                checks.append(
                    f"✗ event name '{actual_event}' != expected '{expected_event}'"
                )

        # ── Check 3: required sub-dict fields present ────────────────────────
        required_map = _REQUIRED_FIELDS.get(intent, {})
        for sub_key, fields in required_map.items():
            sub = event.get(sub_key, {})
            for field in fields:
                total += 1
                if sub.get(field) is not None:
                    checks.append(f"✓ {sub_key}.{field} present")
                    passed += 1
                else:
                    checks.append(f"✗ {sub_key}.{field} missing or null")

        # ── Check 4: data fields not all null ────────────────────────────────
        total += 1
        data = context.get("data", {})
        non_null = sum(1 for v in data.values() if v is not None)
        if non_null > 0:
            checks.append(f"✓ data has {non_null} non-null field(s)")
            passed += 1
        else:
            checks.append("✗ all data fields are null")

        # ── Compute confidence and status ────────────────────────────────────
        confidence = round(passed / total, 2) if total > 0 else 0.0

        if confidence >= 0.85:
            status = "ok"
        elif confidence >= 0.5:
            status = "partial"
        else:
            status = "fail"

        verification = {
            "status":     status,
            "confidence": confidence,
            "checks":     checks,
            "reason":     f"{passed}/{total} checks passed",
        }

        context["verification"] = verification
        logger.info(
            "[VerificationAgent] status=%s confidence=%.2f (%s)",
            status, confidence, verification["reason"]
        )
        return context