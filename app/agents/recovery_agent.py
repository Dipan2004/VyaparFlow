"""
app/agents/recovery_agent.py
-----------------------------
RecoveryAgent — Autonomy Layer, Step 6 (most important).

Implements self-healing logic based on the failure state of the pipeline.

Decision tree:
    if verification.status == "ok"  → no recovery needed
    elif retry_count == 0           → retry (re-run failed agents from history)
    elif retry_count == 1           → fallback (use safe defaults)
    elif retry_count >= 2           → critical escalation, halt retries

The agent does NOT re-run the full pipeline (no circular execution).
Instead it performs a targeted fix:
    RETRY    — re-runs only the agents that errored, one more time
    FALLBACK — fills missing critical fields with safe placeholder values
    ESCALATE — marks context as needing human intervention

Output written to context["recovery"]:
    {
        "action":      "none" | "retry" | "fallback" | "escalate",
        "retry_count": int,
        "details":     str,
        "success":     bool,
    }

context["metadata"]["retry_count"] is incremented on each recovery attempt.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.base_agent import BaseAgent
from app.core.context import add_error

logger = logging.getLogger(__name__)

_MAX_RETRIES = 1   # after this, switch to fallback

# Safe placeholder values used during fallback
_FALLBACK_DEFAULTS: dict[str, Any] = {
    "customer":     "Unknown",
    "item":         "unspecified",
    "quantity":     0,
    "amount":       0,
    "payment_type": None,
    "reason":       "not provided",
    "note":         "recovered by fallback",
}


class RecoveryAgent(BaseAgent):
    """Self-healing agent: retry failed agents, apply fallback, or escalate."""

    name        = "RecoveryAgent"
    input_keys  = ["verification", "errors", "history", "data", "metadata"]
    output_keys = ["recovery", "metadata"]
    action      = "Attempt recovery from pipeline failures"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        verification = context.get("verification", {})
        v_status     = verification.get("status", "ok")
        metadata     = context.setdefault("metadata", {})
        retry_count  = metadata.get("retry_count", 0)

        # ── No recovery needed ───────────────────────────────────────────────
        if v_status == "ok":
            context["recovery"] = {
                "action":      "none",
                "retry_count": retry_count,
                "details":     "Verification passed — no recovery needed",
                "success":     True,
            }
            logger.info("[RecoveryAgent] no recovery needed")
            return context

        # ── Decide recovery strategy ─────────────────────────────────────────
        if retry_count == 0:
            action  = "retry"
            success = self._do_retry(context)
            details = "Retried failed agents"
        elif retry_count <= _MAX_RETRIES:
            action  = "fallback"
            success = self._do_fallback(context)
            details = "Applied safe fallback defaults to missing fields"
        else:
            action  = "escalate"
            success = False
            details = (
                f"Recovery exhausted after {retry_count} attempt(s). "
                "Human intervention required."
            )
            add_error(context, f"[Recovery] {details}")
            logger.error("[RecoveryAgent] escalating — recovery exhausted")

        # Increment retry counter
        metadata["retry_count"] = retry_count + 1

        context["recovery"] = {
            "action":      action,
            "retry_count": retry_count + 1,
            "details":     details,
            "success":     success,
        }

        logger.info(
            "[RecoveryAgent] action=%s retry_count=%d success=%s",
            action, retry_count + 1, success
        )
        return context

    # ── Recovery strategies ──────────────────────────────────────────────────

    def _do_retry(self, context: dict[str, Any]) -> bool:
        """
        Re-run agents that errored in the history.
        Uses the registry to look them up — no direct imports.
        Returns True if at least one agent recovered successfully.
        """
        from app.core.registry import get_agent

        history       = context.get("history", [])
        errored_agents = [
            h["agent"] for h in history if h.get("status") == "error"
        ]

        if not errored_agents:
            logger.info("[RecoveryAgent] retry: no errored agents found in history")
            return True

        recovered = 0
        for agent_name in errored_agents:
            # Find registry key by matching agent name to class name
            key = self._name_to_key(agent_name)
            if not key:
                logger.warning(
                    "[RecoveryAgent] retry: cannot find registry key for '%s'",
                    agent_name
                )
                continue
            try:
                agent = get_agent(key)
                context = agent.run(context)
                logger.info("[RecoveryAgent] retry: '%s' re-ran successfully", agent_name)
                recovered += 1
            except Exception as exc:
                logger.warning(
                    "[RecoveryAgent] retry: '%s' failed again: %s", agent_name, exc
                )

        return recovered > 0

    def _do_fallback(self, context: dict[str, Any]) -> bool:
        """
        Fill missing critical data fields with safe placeholder values.
        Returns True always — fallback is best-effort.
        """
        data    = context.get("data", {})
        intent  = (context.get("intent") or "other").lower()
        filled  = 0

        for field, default in _FALLBACK_DEFAULTS.items():
            if field in data and data[field] is None:
                data[field] = default
                filled += 1
                logger.info(
                    "[RecoveryAgent] fallback: set data['%s'] = %r", field, default
                )

        context["data"] = data
        logger.info("[RecoveryAgent] fallback: filled %d null field(s)", filled)
        return True

    @staticmethod
    def _name_to_key(agent_class_name: str) -> str | None:
        """Map agent class name → registry key."""
        mapping = {
            "IntentAgent":        "intent",
            "ExtractionAgent":    "extraction",
            "ValidationAgent":    "validation",
            "SkillRouterAgent":   "router",
            "LedgerAgent":        "ledger",
            "VerificationAgent":  "verification",
            "MonitorAgent":       "monitor",
            "PredictionAgent":    "prediction",
            "UrgencyAgent":       "urgency",
            "EscalationAgent":    "escalation",
        }
        return mapping.get(agent_class_name)