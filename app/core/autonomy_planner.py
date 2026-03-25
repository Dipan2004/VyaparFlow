"""
app/core/autonomy_planner.py
-----------------------------
Dynamic Autonomy Planner for NotiFlow Autonomous.

Mirrors the design of app/core/planner.py but governs the autonomy layer.
Each rule has a condition that can skip agents based on context state,
avoiding unnecessary work (e.g. skip escalation if priority is low,
skip recovery if verification already passed).

Extending
---------
To add a new autonomy step:
    1. Create app/agents/my_autonomy_agent.py
    2. Register it in app/core/registry.py
    3. Append one AutonomyRule here — zero other changes needed

Public API
----------
build_autonomy_plan(context) -> list[dict]
    Evaluates rules, writes context["autonomy_plan"], returns the plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Rule definition (same pattern as PlanRule in planner.py)
# ---------------------------------------------------------------------------

@dataclass
class AutonomyRule:
    """
    A single conditional step in the autonomy execution plan.

    Attributes:
        agent:       Registry key of the agent to run.
        condition:   callable(ctx) → bool — True means include this agent.
        description: Human-readable reason (written to autonomy_plan entries).
    """
    agent:       str
    condition:   Callable[[dict[str, Any]], bool]
    description: str = ""


# ---------------------------------------------------------------------------
# Condition functions
# ---------------------------------------------------------------------------

def _always(ctx: dict[str, Any]) -> bool:
    return True


def _skip_if_verified(ctx: dict[str, Any]) -> bool:
    """Skip monitor if verification already passed cleanly — nothing to flag."""
    v = ctx.get("verification", {})
    return v.get("status") != "ok"


def _skip_if_no_data(ctx: dict[str, Any]) -> bool:
    """Skip prediction if there is no data to score."""
    return bool(ctx.get("data"))


def _skip_if_low_score(ctx: dict[str, Any]) -> bool:
    """Skip urgency if priority score is already 0 and intent is 'other'."""
    intent = (ctx.get("intent") or "other").lower()
    if intent == "other" and ctx.get("priority_score", 0) == 0:
        return False   # nothing will change — skip
    return True


def _escalation_needed(ctx: dict[str, Any]) -> bool:
    """
    Only run escalation if priority is high/critical OR risk is high.
    Avoids noisy alert logs on routine transactions.
    """
    priority = (ctx.get("priority") or "normal").lower()
    risk     = ctx.get("risk", {}).get("level", "low")
    return priority in ("high", "critical") or risk == "high"


def _recovery_needed(ctx: dict[str, Any]) -> bool:
    """
    Run recovery only if something actually went wrong.
    Skipped if verification passed and no errors exist.
    """
    v_status = ctx.get("verification", {}).get("status", "ok")
    errors   = ctx.get("errors", [])
    return v_status != "ok" or len(errors) > 0


# ---------------------------------------------------------------------------
# Rule set  (order matters — this IS the autonomy pipeline definition)
# ---------------------------------------------------------------------------

_AUTONOMY_RULES: list[AutonomyRule] = [
    AutonomyRule(
        agent       = "verification",
        condition   = _always,
        description = "Validate skill execution produced expected output",
    ),
    AutonomyRule(
        agent       = "monitor",
        condition   = _skip_if_verified,
        description = "Scan for missing fields, errors, and inconsistencies",
    ),
    AutonomyRule(
        agent       = "prediction",
        condition   = _skip_if_no_data,
        description = "Rule-based risk scoring on extracted data",
    ),
    AutonomyRule(
        agent       = "urgency",
        condition   = _skip_if_low_score,
        description = "Detect urgency signals and derive final priority label",
    ),
    AutonomyRule(
        agent       = "escalation",
        condition   = _escalation_needed,
        description = "Raise alerts for high-priority or high-risk situations",
    ),
    AutonomyRule(
        agent       = "recovery",
        condition   = _recovery_needed,
        description = "Attempt self-healing for pipeline failures",
    ),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_autonomy_plan(context: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Evaluate autonomy rules against the current context.

    Writes the plan to context["autonomy_plan"] and returns it.

    Args:
        context: The live request context dict (after main pipeline ran).

    Returns:
        Ordered list of autonomy steps, each a dict:
            {
                "agent":       str,   # registry key
                "description": str,   # human-readable reason
            }
    """
    plan = []
    for rule in _AUTONOMY_RULES:
        if rule.condition(context):
            plan.append({
                "agent":       rule.agent,
                "description": rule.description,
            })
    context["autonomy_plan"] = plan
    return plan