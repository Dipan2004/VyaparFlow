"""
app/agents/monitor_agent.py
----------------------------
MonitorAgent — Autonomy Layer, Step 2.

Scans the context after main pipeline execution and detects:
    - missing required fields for the intent
    - agents that errored in history
    - inconsistencies (e.g. payment event but no amount in data)
    - pipeline state anomalies

Appends findings to context["errors"] (non-fatal) and writes a
structured summary to context["monitor"].

Output written to context["monitor"]:
    {
        "issues":   list[str],   # all detected problems
        "warnings": list[str],   # non-critical observations
        "healthy":  bool,        # True if no hard issues found
    }
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.base_agent import BaseAgent
from app.core.context import add_error

logger = logging.getLogger(__name__)

# Fields that must not be null for each intent to be considered healthy
_CRITICAL_FIELDS: dict[str, list[str]] = {
    "order":       ["item"],
    "payment":     ["amount"],
    "credit":      ["customer"],
    "return":      ["reason"],
    "preparation": ["item"],
}


class MonitorAgent(BaseAgent):
    """Detect failures, missing data, and pipeline inconsistencies."""

    name        = "MonitorAgent"
    input_keys  = ["intent", "data", "event", "history", "errors", "state"]
    output_keys = ["monitor"]
    action      = "Scan pipeline results for failures and inconsistencies"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        issues:   list[str] = []
        warnings: list[str] = []

        intent  = (context.get("intent") or "other").lower()
        data    = context.get("data", {})
        event   = context.get("event", {})
        history = context.get("history", [])
        state   = context.get("state", "unknown")

        # ── Check 1: pipeline state ──────────────────────────────────────────
        if state == "failed":
            issues.append(f"Pipeline ended in failed state")
        elif state == "partial":
            warnings.append("Pipeline ended in partial state — some steps may have been skipped")

        # ── Check 2: agent errors in history ────────────────────────────────
        errored_agents = [
            h["agent"] for h in history if h.get("status") == "error"
        ]
        for agent_name in errored_agents:
            issues.append(f"Agent '{agent_name}' reported an error during execution")

        # ── Check 3: missing critical fields ────────────────────────────────
        critical = _CRITICAL_FIELDS.get(intent, [])
        for field in critical:
            if data.get(field) is None:
                issues.append(
                    f"Critical field '{field}' is null for intent '{intent}'"
                )

        # ── Check 4: empty event after routing ──────────────────────────────
        routed = any(
            h["agent"] == "SkillRouterAgent" and h.get("status") == "success"
            for h in history
        )
        if routed and not event:
            issues.append("SkillRouterAgent completed but event dict is empty")

        # ── Check 5: intent/event consistency ───────────────────────────────
        event_name = event.get("event", "")
        if intent == "payment" and event_name and "payment" not in event_name:
            warnings.append(
                f"Intent is 'payment' but event name is '{event_name}'"
            )
        if intent == "order" and event_name and "order" not in event_name:
            warnings.append(
                f"Intent is 'order' but event name is '{event_name}'"
            )

        # ── Check 6: duplicate errors already in context ────────────────────
        existing_errors = context.get("errors", [])
        if len(existing_errors) > 3:
            warnings.append(
                f"{len(existing_errors)} errors already accumulated in context"
            )

        # ── Write new issues as context errors ───────────────────────────────
        for issue in issues:
            add_error(context, f"[Monitor] {issue}")

        healthy = len(issues) == 0
        monitor = {
            "issues":   issues,
            "warnings": warnings,
            "healthy":  healthy,
        }

        context["monitor"] = monitor
        logger.info(
            "[MonitorAgent] healthy=%s issues=%d warnings=%d",
            healthy, len(issues), len(warnings)
        )
        return context