"""
app/agents/escalation_agent.py
-------------------------------
EscalationAgent — Autonomy Layer, Step 5.

Triggers when priority is "high"/"critical" OR risk is "high".
Logs structured alerts and simulates an external notification.

In production, replace _notify() with a real webhook/SMS/email call.

Output written to context["alerts"]:
    [
        {
            "level":     "warning" | "critical",
            "trigger":   str,          # what caused this alert
            "message":   str,          # human-readable description
            "timestamp": str,          # ISO-8601
            "notified":  bool,         # True if notification was "sent"
        },
        ...
    ]
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.base_agent import BaseAgent

logger = logging.getLogger(__name__)

_ESCALATION_PRIORITIES = {"high", "critical"}
_ESCALATION_RISKS      = {"high"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EscalationAgent(BaseAgent):
    """Detect high-priority or high-risk situations and raise alerts."""

    name        = "EscalationAgent"
    input_keys  = ["priority", "risk", "errors", "intent", "data"]
    output_keys = ["alerts"]
    action      = "Raise alerts and simulate notifications for critical situations"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        priority = (context.get("priority") or "low").lower()
        risk     = context.get("risk", {})
        errors   = context.get("errors", [])
        intent   = (context.get("intent") or "other").lower()
        data     = context.get("data", {})

        alerts: list[dict[str, Any]] = []

        # ── Trigger 1: high priority score (was "critical" in old model) ─────
        score = context.get("priority_score", 0)
        if score >= 80:
            alert = self._build_alert(
                level   = "critical",
                trigger = f"priority_score={score}",
                message = (
                    f"CRITICAL priority score {score}/100. "
                    f"Intent: {intent}. "
                    f"Customer: {data.get('customer', 'unknown')}."
                ),
            )
            alerts.append(alert)
            self._notify(alert)

        # ── Trigger 2: high priority label ───────────────────────────────────
        elif priority == "high":
            alert = self._build_alert(
                level   = "warning",
                trigger = f"priority=high score={score}",
                message = (
                    f"High priority transaction flagged. "
                    f"Intent: {intent}. "
                    f"Score: {score}/100. "
                    f"Reason: {context.get('metadata', {}).get('urgency_reason', 'n/a')}."
                ),
            )
            alerts.append(alert)
            self._notify(alert)

        # ── Trigger 3: high risk ─────────────────────────────────────────────
        if risk.get("level") in _ESCALATION_RISKS:
            risk_reasons = "; ".join(risk.get("reasons", []))
            alert = self._build_alert(
                level   = "warning",
                trigger = "risk=high",
                message = f"High risk transaction. Reasons: {risk_reasons}",
            )
            alerts.append(alert)
            self._notify(alert)

        # ── Trigger 4: critical errors in pipeline ───────────────────────────
        critical_errors = [e for e in errors if "[Monitor]" in e]
        if len(critical_errors) >= 2:
            alert = self._build_alert(
                level   = "warning",
                trigger = "monitor_issues",
                message = (
                    f"{len(critical_errors)} monitor issue(s) detected: "
                    f"{critical_errors[0]}"
                ),
            )
            alerts.append(alert)

        context["alerts"] = alerts
        if alerts:
            logger.warning(
                "[EscalationAgent] %d alert(s) raised (priority=%s risk=%s)",
                len(alerts), priority, risk.get("level", "unknown")
            )
        else:
            logger.info("[EscalationAgent] no escalation needed")
        return context

    @staticmethod
    def _build_alert(level: str, trigger: str, message: str) -> dict[str, Any]:
        return {
            "level":     level,
            "trigger":   trigger,
            "message":   message,
            "timestamp": _now_iso(),
            "notified":  False,   # updated by _notify()
        }

    @staticmethod
    def _notify(alert: dict[str, Any]) -> None:
        """
        Simulate sending an external notification.
        Replace this method with a real webhook/SMS/email integration.
        """
        alert["notified"] = True
        logger.warning(
            "[EscalationAgent] 🚨 ALERT [%s] %s",
            alert["level"].upper(), alert["message"]
        )