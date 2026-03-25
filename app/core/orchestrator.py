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

from app.core.context          import create_context, update_context, log_step, add_error
from app.core.planner          import build_plan
from app.core.autonomy_planner import build_autonomy_plan
from app.core.priority         import reset_priority_score
from app.core.registry         import get_agent

logger = logging.getLogger(__name__)

_MAX_REPLANS = 2   # hard cap on feedback-loop iterations


def process_message(message: str, source: str = "system") -> dict[str, Any]:
    """
    Run a raw business message through the full NotiFlow agent pipeline.

    Phase 2: main pipeline driven by Planner (dynamic).
    Phase 3: autonomy layer driven by AutonomyPlanner (dynamic).
    Fix:     feedback loop — replan up to _MAX_REPLANS times if needed.

    Args:
        message: Raw Hinglish or English business message.
        source:  Notification source (e.g. "whatsapp", "gpay").

    Returns:
        Flat result dict + full context.

    Raises:
        ValueError: Empty message.
    """
    if not message or not message.strip():
        raise ValueError("Message cannot be empty.")

    ctx = create_context(message.strip(), source=source)
    logger.info("Orchestrator ← %r (source=%s)", message, source)

    # ── Main plan + autonomy + feedback loop ──────────────────────────────
    while True:
        retry_count = ctx["metadata"].get("retry_count", 0)

        # ── 1. Build and run main plan ────────────────────────────────────
        plan = build_plan(ctx)
        logger.info(
            "[cycle=%d] Main plan: [%s]",
            retry_count,
            ", ".join(s["agent"] for s in plan),
        )
        ctx = _run_plan(ctx, plan)

        # ── 2. Build and run autonomy plan ────────────────────────────────
        autonomy_plan = build_autonomy_plan(ctx)
        logger.info(
            "[cycle=%d] Autonomy plan: [%s]",
            retry_count,
            ", ".join(s["agent"] for s in autonomy_plan),
        )
        ctx = _run_autonomy(ctx, autonomy_plan)

        # ── 3. Check if replan is needed ──────────────────────────────────
        if retry_count >= _MAX_REPLANS:
            logger.info("Replan cap reached (%d) — stopping loop.", _MAX_REPLANS)
            break

        if not _should_replan(ctx):
            logger.info("[cycle=%d] No replan needed.", retry_count)
            break

        # ── 4. Prepare for replan ─────────────────────────────────────────
        logger.warning(
            "[cycle=%d] Replan triggered — retry_count → %d",
            retry_count, retry_count + 1,
        )
        ctx["metadata"]["retry_count"] = retry_count + 1

        # Reset priority score so contributors don't double-count
        reset_priority_score(ctx)

        # Clear autonomy outputs so fresh evaluation happens
        for key in ("verification", "monitor", "risk", "alerts", "recovery"):
            ctx.pop(key, None)

        # Clear accumulated errors from previous cycle (keep original errors)
        ctx["errors"] = [e for e in ctx["errors"] if not e.startswith("[Monitor]")]

    # ── Mark final state ──────────────────────────────────────────────────
    if ctx.get("state") not in ("failed",):
        update_context(ctx, state="completed")

    logger.info(
        "Orchestrator done → state=%s intents=%s errors=%d risk=%s priority=%s score=%d",
        ctx["state"],
        ctx.get("intents", [ctx.get("intent")]),
        len(ctx["errors"]),
        ctx.get("risk", {}).get("level", "n/a"),
        ctx.get("priority", "n/a"),
        ctx.get("priority_score", 0),
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


def _run_autonomy(ctx: dict[str, Any], plan: list[dict]) -> dict[str, Any]:
    """
    Run the dynamically planned autonomy sequence.

    All autonomy agents are non-critical — failures are recorded but
    never abort the sequence or corrupt the main pipeline result.
    """
    for step in plan:
        agent_key = step["agent"]
        try:
            agent = get_agent(agent_key)
        except KeyError:
            logger.warning("[Autonomy] agent '%s' not in registry — skipping", agent_key)
            continue
        try:
            ctx = agent.run(ctx)
        except Exception as exc:
            logger.error("[Autonomy] '%s' raised %s — continuing", agent_key, exc)
            add_error(ctx, f"[Autonomy] {agent_key} failed: {exc}")
            if ctx.get("state") == "failed":
                update_context(ctx, state="partial")
    return ctx


def _should_replan(ctx: dict[str, Any]) -> bool:
    """
    Return True if the feedback loop should trigger a replan.

    Conditions (any one is sufficient):
        1. verification.status == "fail"
        2. risk.level          == "high"
        3. errors list is non-empty (excluding autonomy-internal noise)
    """
    v_status = ctx.get("verification", {}).get("status", "ok")
    if v_status == "fail":
        logger.info("[Feedback] replan trigger: verification=fail")
        return True

    risk_level = ctx.get("risk", {}).get("level", "low")
    if risk_level == "high":
        logger.info("[Feedback] replan trigger: risk=high")
        return True

    # Only count errors that are not pure autonomy-internal noise
    meaningful_errors = [
        e for e in ctx.get("errors", [])
        if not e.startswith("[Autonomy]")
    ]
    if meaningful_errors:
        logger.info(
            "[Feedback] replan trigger: %d meaningful error(s)", len(meaningful_errors)
        )
        return True

    return False


def _build_result(ctx: dict[str, Any]) -> dict[str, Any]:
    """Flatten context into the public API response shape."""
    return {
        # ── Core (backward compatible) ────────────────────────────────────
        "message":       ctx["message"],
        "intent":        ctx.get("intent") or "other",
        "intents":       ctx.get("intents") or [ctx.get("intent") or "other"],
        "data":          ctx.get("data", {}),
        "multi_data":    ctx.get("multi_data", {}),
        "event":         ctx.get("event", {}),
        "sheet_updated": ctx.get("metadata", {}).get("sheet_updated", False),
        # ── Autonomy fields ───────────────────────────────────────────────
        "verification":  ctx.get("verification", {}),
        "risk":          ctx.get("risk", {}),
        "priority":      ctx.get("priority", "low"),
        "priority_score": ctx.get("priority_score", 0),
        "alerts":        ctx.get("alerts", []),
        "recovery":      ctx.get("recovery", {}),
        "monitor":       ctx.get("monitor", {}),
        # ── Debug ─────────────────────────────────────────────────────────
        "context":       ctx,
    }