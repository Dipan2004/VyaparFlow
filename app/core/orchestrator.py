"""
app/core/orchestrator.py
------------------------
Dynamic Agent Orchestrator for NotiFlow Autonomous (Phase 2).

Replaces the static pipeline list with a planner-driven execution loop.

Flow
----
    create_context()
        ↓
    build_plan(ctx)          ← Planner evaluates rules, writes ctx["plan"]
        ↓
    for step in ctx["plan"]:
        agent = AGENT_REGISTRY[step["agent"]]
        agent.run(ctx)       ← executes, writes audit entry to ctx["history"]
        if failed and step["critical"]: abort
        ↓
    _build_result(ctx)       ← flatten ctx → public API response shape

Key properties
--------------
- No hardcoded execution order anywhere in this file
- LedgerAgent is NOT special-cased — it is just another plan step
- Adding a new agent = one registry entry + one planner rule, zero changes here
- Non-critical step failures are recorded and skipped, not aborted

Return shape (backward compatible):
    {
        "message":       str,
        "intent":        str,
        "data":          dict,
        "event":         dict,
        "sheet_updated": bool,
        "context":       dict,  ← full context (debug/audit)
    }
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.context  import create_context, update_context, log_step, add_error
from app.core.planner  import build_plan
from app.core.registry import get_agent

logger = logging.getLogger(__name__)

# Autonomy layer — runs after every main pipeline execution.
# Order matters: verification → monitor → prediction → urgency → escalation → recovery
_AUTONOMY_SEQUENCE = [
    "verification",
    "monitor",
    "prediction",
    "urgency",
    "escalation",
    "recovery",
]


def process_message(message: str, source: str = "system") -> dict[str, Any]:
    """
    Run a raw business message through the full NotiFlow agent pipeline.

    Phase 2: execution order determined by Planner (dynamic).
    Phase 3: autonomy layer runs after main pipeline (fixed sequence).

    Args:
        message: Raw Hinglish or English business message.
        source:  Notification source (e.g. "whatsapp", "gpay").

    Returns:
        Flat result dict matching the existing API contract + full context.

    Raises:
        ValueError: Empty message.
    """
    if not message or not message.strip():
        raise ValueError("Message cannot be empty.")

    # ── 1. Initialise context ─────────────────────────────────────────────
    ctx = create_context(message.strip(), source=source)
    logger.info("Orchestrator ← %r (source=%s)", message, source)

    # ── 2. Build execution plan ───────────────────────────────────────────
    plan = build_plan(ctx)
    logger.info(
        "Execution plan: [%s]",
        ", ".join(step["agent"] for step in plan)
    )

    # ── 3. Execute main plan dynamically ─────────────────────────────────
    ctx = _run_plan(ctx, plan)

    # ── 4. Execute autonomy layer ─────────────────────────────────────────
    logger.info("Autonomy layer starting")
    ctx = _run_autonomy(ctx)

    # ── 5. Mark completed if not already failed ───────────────────────────
    if ctx.get("state") not in ("failed",):
        update_context(ctx, state="completed")

    logger.info(
        "Orchestrator → state=%s  intent=%s  errors=%d  risk=%s  priority=%s",
        ctx["state"],
        ctx.get("intent"),
        len(ctx["errors"]),
        ctx.get("risk", {}).get("level", "n/a"),
        ctx.get("priority", "n/a"),
    )

    return _build_result(ctx)


def _run_plan(ctx: dict[str, Any], plan: list[dict]) -> dict[str, Any]:
    """Execute the planner-generated main pipeline steps."""
    for step in plan:
        agent_key   = step["agent"]
        is_critical = step.get("critical", True)

        try:
            agent = get_agent(agent_key)
        except KeyError as exc:
            msg = f"Orchestrator: {exc}"
            logger.error(msg)
            add_error(ctx, msg)
            log_step(ctx, agent_key, "skipped",
                     detail=f"Agent not found in registry: {agent_key}")
            if is_critical:
                update_context(ctx, state="failed")
                break
            continue

        try:
            ctx = agent.run(ctx)
        except Exception as exc:
            logger.error("Orchestrator: %s raised %s", agent_key, exc)
            if is_critical:
                logger.error("Critical agent '%s' failed — aborting pipeline.", agent_key)
                break
            else:
                logger.warning("Non-critical agent '%s' failed — continuing.", agent_key)
                if ctx.get("state") == "failed":
                    update_context(ctx, state="partial")
                continue

        if ctx.get("state") == "failed" and is_critical:
            logger.error("Pipeline in failed state after critical agent '%s'.", agent_key)
            break

    return ctx


def _run_autonomy(ctx: dict[str, Any]) -> dict[str, Any]:
    """
    Run the fixed autonomy sequence.

    All autonomy agents are non-critical — a failure in any one of them
    never aborts the sequence or changes the main pipeline result.
    """
    for agent_key in _AUTONOMY_SEQUENCE:
        try:
            agent = get_agent(agent_key)
        except KeyError:
            logger.warning("[Autonomy] agent '%s' not in registry — skipping", agent_key)
            continue
        try:
            ctx = agent.run(ctx)
        except Exception as exc:
            # Autonomy agents must never crash the response
            logger.error("[Autonomy] agent '%s' raised %s — continuing", agent_key, exc)
            add_error(ctx, f"[Autonomy] {agent_key} failed: {exc}")
            # Reset state if autonomy agent set it to failed
            if ctx.get("state") == "failed":
                update_context(ctx, state="partial")

    return ctx


def _build_result(ctx: dict[str, Any]) -> dict[str, Any]:
    """Flatten context into the public API response shape."""
    return {
        # ── Core (backward compatible) ────────────────────────────────────
        "message":       ctx["message"],
        "intent":        ctx.get("intent") or "other",
        "data":          ctx.get("data", {}),
        "event":         ctx.get("event", {}),
        "sheet_updated": ctx.get("metadata", {}).get("sheet_updated", False),
        # ── Phase 3: Autonomy fields ──────────────────────────────────────
        "verification":  ctx.get("verification", {}),
        "risk":          ctx.get("risk", {}),
        "priority":      ctx.get("priority", "normal"),
        "alerts":        ctx.get("alerts", []),
        "recovery":      ctx.get("recovery", {}),
        "monitor":       ctx.get("monitor", {}),
        # ── Debug ─────────────────────────────────────────────────────────
        "context":       ctx,
    }