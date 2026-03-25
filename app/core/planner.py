"""
app/core/planner.py
-------------------
Decision Engine (Planner) for NotiFlow Autonomous.

Converts a context snapshot into an ordered execution plan.

Design
------
The planner uses an ordered list of PlanRule objects.  Each rule has:
    - agent:     registry key of the agent to run
    - condition: callable(context) → bool
                 True  = include this agent in the plan
                 False = skip it
    - critical:  if True, a failure from this agent aborts the pipeline
                 if False, failure is recorded but execution continues

Plan output shape (written to context["plan"]):
    [
        {"agent": "intent",     "critical": True},
        {"agent": "extraction", "critical": True},
        {"agent": "validation", "critical": True},
        {"agent": "router",     "critical": True},
        {"agent": "ledger",     "critical": False},
    ]

Skipping logic (avoids redundant work on re-entry):
    - "intent"     skipped if context["intent"] is already set
    - "extraction" skipped if context["data"] is already non-empty
    - "validation" skipped if context["state"] == "validated"
    - "router"     skipped if context["event"] is already non-empty
    - "ledger"     always included (idempotent sync)

Extending
---------
To add a new step, append one PlanRule to _RULES.  No other file changes.

Public API
----------
build_plan(context) -> list[dict]
    Returns the ordered plan list and writes it to context["plan"].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Rule definition
# ---------------------------------------------------------------------------

@dataclass
class PlanRule:
    """
    A single conditional step in the execution plan.

    Attributes:
        agent:     Key in AGENT_REGISTRY to execute.
        condition: callable(ctx) → bool — True means "include this agent".
        critical:  If True, failure aborts the rest of the pipeline.
                   If False, failure is logged and execution continues.
        description: Human-readable reason for this rule (for audit logs).
    """
    agent:       str
    condition:   Callable[[dict[str, Any]], bool]
    critical:    bool = True
    description: str  = ""


# ---------------------------------------------------------------------------
# Rule set  (order matters — this IS the pipeline definition)
# ---------------------------------------------------------------------------

def _intent_needed(ctx: dict[str, Any]) -> bool:
    """Run intent detection unless intent is already resolved."""
    return not ctx.get("intent")


def _extraction_needed(ctx: dict[str, Any]) -> bool:
    """Run extraction unless structured data already exists for all detected intents."""
    if not ctx.get("data") and not ctx.get("multi_data"):
        return True
    # On replan: re-extract if intents changed or multi_data is missing entries
    intents   = ctx.get("intents") or []
    multi_data = ctx.get("multi_data", {})
    if intents and any(i not in multi_data for i in intents):
        return True
    return False


def _validation_needed(ctx: dict[str, Any]) -> bool:
    """Run validation unless already validated."""
    return ctx.get("state") != "validated"


def _routing_needed(ctx: dict[str, Any]) -> bool:
    """Run skill router unless a skill event already exists."""
    return not ctx.get("event")


def _ledger_needed(ctx: dict[str, Any]) -> bool:
    """
    Run ledger sync unless the pipeline failed before routing.
    We still attempt it on partial failures so any partial data is recorded.
    """
    return True   # always attempt — LedgerAgent is non-fatal anyway


_RULES: list[PlanRule] = [
    PlanRule(
        agent       = "intent",
        condition   = _intent_needed,
        critical    = True,
        description = "Classify business intent from message",
    ),
    PlanRule(
        agent       = "extraction",
        condition   = _extraction_needed,
        critical    = True,
        description = "Extract structured fields from message",
    ),
    PlanRule(
        agent       = "validation",
        condition   = _validation_needed,
        critical    = True,
        description = "Normalise and validate extracted data",
    ),
    PlanRule(
        agent       = "router",
        condition   = _routing_needed,
        critical    = True,
        description = "Route to business skill and execute",
    ),
    PlanRule(
        agent       = "ledger",
        condition   = _ledger_needed,
        critical    = False,   # Sheets failure must never crash the pipeline
        description = "Sync transaction to Google Sheets ledger",
    ),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_plan(context: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Evaluate rules against the current context and produce an execution plan.

    Writes the plan to context["plan"] and also returns it.

    Args:
        context: The live request context dict.

    Returns:
        Ordered list of plan steps, each a dict with:
            {
                "agent":       str,   # registry key
                "critical":    bool,  # abort pipeline on failure?
                "description": str,   # human-readable reason
            }

    Example:
        >>> ctx = create_context("rahul ne 15000 bheja")
        >>> build_plan(ctx)
        [
            {"agent": "intent",     "critical": True,  "description": "..."},
            {"agent": "extraction", "critical": True,  "description": "..."},
            {"agent": "validation", "critical": True,  "description": "..."},
            {"agent": "router",     "critical": True,  "description": "..."},
            {"agent": "ledger",     "critical": False, "description": "..."},
        ]
    """
    plan = []
    for rule in _RULES:
        if rule.condition(context):
            plan.append({
                "agent":       rule.agent,
                "critical":    rule.critical,
                "description": rule.description,
            })
    context["plan"] = plan
    return plan
