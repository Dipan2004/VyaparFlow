"""
app/core/context.py
-------------------
Unified request context for NotiFlow Autonomous.

The context object is the single source of truth for every request.
It is created at the API boundary, threaded through every agent, and
returned to the caller as part of the final response.

Structure
---------
{
    "message":   str,           # original raw message
    "intent":    str | None,    # detected intent (filled by IntentAgent)
    "data":      dict,          # extracted + validated fields
    "event":     dict,          # skill execution result
    "state":     str,           # pipeline lifecycle state
    "history":   list[dict],    # audit-level agent execution log  ← UPGRADED
    "errors":    list[str],     # non-fatal errors accumulated during run
    "priority":  str,           # "normal" | "high" | "low"
    "plan":      list[dict],    # ordered plan steps (set by Planner)
    "metadata":  dict,          # source, sheet_updated, model, etc.
}

History entry shape (audit-ready):
    {
        "agent":       str,       # agent name
        "action":      str,       # what the agent did (human-readable)
        "input_keys":  list[str], # context keys read by this agent
        "output_keys": list[str], # context keys written by this agent
        "status":      str,       # "success" | "error" | "skipped"
        "detail":      str,       # error message or extra note
        "timestamp":   str,       # ISO-8601 UTC
    }

Pipeline states:
    initialized → intent_detected → extracted → validated → routed → completed
    Any stage can transition to: failed

Public API (unchanged from Phase 1 — fully backward compatible)
----------
create_context(message, source) -> dict
update_context(ctx, **kwargs)   -> dict
log_step(ctx, agent, status, detail, *, action, input_keys, output_keys) -> None
add_error(ctx, error) -> None
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_context(message: str, source: str = "system") -> dict[str, Any]:
    """
    Create a fresh request context for a new message.

    Args:
        message: Raw business message (Hinglish or English).
        source:  Notification source (e.g. "whatsapp", "gpay").

    Returns:
        Fully initialised context dict.
    """
    return {
        "message":  message.strip(),
        "intent":   None,
        "data":     {},
        "event":    {},
        "state":    "initialized",
        "history":  [],
        "errors":   [],
        "priority": "normal",
        # plan is [] until Planner fills it; list[dict] in Phase 2
        "plan":     [],
        "metadata": {
            "source":        source,
            "sheet_updated": False,
            "model":         None,
            "created_at":    datetime.now(timezone.utc).isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# Mutators
# ---------------------------------------------------------------------------

def update_context(ctx: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """
    Apply keyword updates to the context (in-place, returns ctx).

    Supports double-underscore for nested dicts:
        update_context(ctx, metadata__source="whatsapp")
        update_context(ctx, intent="order", state="intent_detected")
    """
    for key, value in kwargs.items():
        if "__" in key:
            parent, child = key.split("__", 1)
            if parent in ctx and isinstance(ctx[parent], dict):
                ctx[parent][child] = value
        else:
            ctx[key] = value
    return ctx


def log_step(
    ctx:         dict[str, Any],
    agent:       str,
    status:      str,
    detail:      str = "",
    *,
    action:      str = "",
    input_keys:  list[str] | None = None,
    output_keys: list[str] | None = None,
) -> None:
    """
    Append an audit-level execution entry to context["history"].

    Backward compatible: the original 4-arg signature still works.
    New callers can supply keyword-only audit fields for richer logs.

    Args:
        ctx:         The active context dict.
        agent:       Agent name (e.g. "IntentAgent").
        status:      "success" | "error" | "skipped".
        detail:      Error message or human-readable note.
        action:      What the agent did (e.g. "classified intent as payment").
        input_keys:  Context keys the agent READ  (e.g. ["message"]).
        output_keys: Context keys the agent WROTE (e.g. ["intent", "state"]).
    """
    ctx["history"].append({
        "agent":       agent,
        "action":      action or f"{agent} executed",
        "input_keys":  input_keys  or [],
        "output_keys": output_keys or [],
        "status":      status,
        "detail":      detail,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    })


def add_error(ctx: dict[str, Any], error: str) -> None:
    """Record a non-fatal error in context["errors"]."""
    ctx["errors"].append(error)
