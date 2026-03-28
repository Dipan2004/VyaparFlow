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

from app.config                import DEMO_MODE
from app.core.context          import create_context, update_context, log_step, add_error
from app.core.event_bus        import emit_event, emit_notification, push_live_log
from app.core.planner          import build_plan
from app.core.autonomy_planner import build_autonomy_plan
from app.core.priority         import reset_priority_score
from app.core.registry         import get_agent

logger = logging.getLogger(__name__)

_MAX_REPLANS = 2   # hard cap on feedback-loop iterations

_STEP_EVENT_MAP: dict[str, tuple[str, str]] = {
    "intent": ("intent_detected", "IntentAgent"),
    "extraction": ("extraction_done", "ExtractionAgent"),
    "validation": ("validation_done", "ValidationAgent"),
    "invoice_agent": ("invoice_generated", "InvoiceAgent"),
    "payment_agent": ("payment_requested", "PaymentAgent"),
    "ledger": ("execution_done", "LedgerAgent"),
    "recovery": ("recovery_triggered", "RecoveryAgent"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Demo Mode Support (for API when DEMO_MODE=true)
# ─────────────────────────────────────────────────────────────────────────────

_DEMO_RESPONSES: dict[str, dict] = {
    "new order": {
        "intent": "order",
        "data": {"customer": None, "item": "goods", "quantity": 1},
        "event": {"event": "order_received", "order": {"status": "pending"}},
    },
    "order": {
        "intent": "order",
        "data": {"customer": None, "item": "goods", "quantity": 1},
        "event": {"event": "order_received", "order": {"status": "pending"}},
    },
    "bhej": {
        "intent": "order",
        "data": {"customer": None, "item": "goods", "quantity": 1},
        "event": {"event": "order_received", "order": {"status": "pending"}},
    },
    "bheja": {
        "intent": "order",
        "data": {"customer": None, "item": "goods", "quantity": 1},
        "event": {"event": "order_received", "order": {"status": "pending"}},
    },
    "payment": {
        "intent": "payment",
        "data": {"customer": None, "amount": 0, "payment_type": None},
        "event": {"event": "payment_recorded", "payment": {"status": "received"}},
    },
    "kiya": {
        "intent": "payment",
        "data": {"customer": None, "amount": 0, "payment_type": None},
        "event": {"event": "payment_recorded", "payment": {"status": "received"}},
    },
    "return": {
        "intent": "return",
        "data": {"customer": None, "item": None, "reason": "other"},
        "event": {"event": "return_requested", "return": {"status": "pending_review"}},
    },
    "credit": {
        "intent": "credit",
        "data": {"customer": None, "amount": None},
        "event": {"event": "credit_recorded", "credit": {"status": "open"}},
    },
    "preparation": {
        "intent": "preparation",
        "data": {"item": "goods", "quantity": 1},
        "event": {"event": "preparation_queued", "preparation": {"status": "queued"}},
    },
}


def _demo_response(message: str) -> tuple[str, dict]:
    """Get a demo response based on message keywords."""
    m = message.lower()
    for keyword, response in _DEMO_RESPONSES.items():
        if keyword in m:
            return response["intent"], response
    return "other", {
        "intent": "other",
        "data": {},
        "event": {"event": "message_processed", "status": "no_action"},
    }


def process_message_demo(message: str, source: str = "system") -> dict[str, Any]:
    """
    Demo mode: Return instant mock response without calling any LLM.
    Useful for testing and when NVIDIA NIM API is slow or unavailable.
    """
    ctx = create_context(message.strip(), source=source)
    intent, response_data = _demo_response(message)
    
    ctx["intent"] = intent
    ctx["intents"] = [intent]
    ctx["data"] = response_data.get("data", {})
    ctx["event"] = response_data.get("event", {})
    ctx["state"] = "execution_done"
    ctx["demo_mode"] = True
    
    logger.info("[DEMO MODE] Intent=%s, Message=%r", intent, message)
    
    return _build_result(ctx)



def process_message(
    message: str,
    source: str = "system",
    step_callback=None,
) -> dict[str, Any]:
    """
    Run a raw business message through the full NotiFlow agent pipeline.

    Phase 2: main pipeline driven by Planner (dynamic).
    Phase 3: autonomy layer driven by AutonomyPlanner (dynamic).
    Fix:     feedback loop — replan up to _MAX_REPLANS times if needed.

    Args:
        message:       Raw Hinglish or English business message.
        source:        Notification source (e.g. "whatsapp", "gpay").
        step_callback: Optional callable(payload: dict) invoked after each
                       pipeline step completes.  Used by the API layer to
                       stream incremental updates to connected clients.
                       Must be thread-safe — it is called from the executor
                       thread.  Failures are silently ignored.

    Returns:
        Flat result dict + full context.

    Raises:
        ValueError: Empty message.
    """
    if not message or not message.strip():
        raise ValueError("Message cannot be empty.")

    # ALWAYS run through orchestrator - no bypass allowed
    ctx = create_context(message.strip(), source=source)

    # Store the step callback so _emit_pipeline_step_event can invoke it.
    # The key is prefixed with "_" to mark it as internal/non-serialisable.
    if step_callback is not None:
        ctx["_step_callback"] = step_callback

    logger.info("Orchestrator ← %r (source=%s)", message, source)
    _emit_pipeline_event(
        ctx,
        "message_received",
        {
            "message": ctx["message"],
            "source": source,
            "state": ctx.get("state"),
        },
        agent="Orchestrator",
        step="message",
        message=f"Received message from {source}",
        log_text=f"[Orchestrator] Message received from {source}: {ctx['message']}",
    )

    # STEP 0: Emit intent started immediately - real-time feedback
    _emit_pipeline_step_event(ctx, "intent", "started", "Intent detection started")

    # ── Emit pipeline started event ───────────────────────────────────────
    emit_event(
        ctx,
        "pipeline_status",
        {
            "status": "started",
            "message": message,
            "source": source,
        },
        agent="Orchestrator",
        step="pipeline",
        message="Pipeline execution started",
    )

    # ── Main plan + autonomy + feedback loop ──────────────────────────────
    while True:
        retry_count = ctx["metadata"].get("retry_count", 0)

        # ── 1. Build and run main plan ────────────────────────────────────
        # IMPORTANT: Always build the plan AFTER intent is known
        # First pass: intent might be None, so we need to rebuild after running intent agent
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
        _emit_pipeline_event(
            ctx,
            "recovery_triggered",
            {
                "retry_count": retry_count + 1,
                "reason": "replan_required",
                "errors": ctx.get("errors", []),
            },
            agent="RecoveryAgent",
            step="recovery",
            message="Recovery triggered after pipeline replan request",
            log_text=f"[RecoveryAgent] Recovery triggered after cycle {retry_count}",
        )
        ctx["metadata"]["retry_count"] = retry_count + 1

        # Reset priority score so contributors don't double-count
        reset_priority_score(ctx)

        # Clear autonomy outputs so fresh evaluation happens
        for key in ("verification", "monitor", "risk", "alerts", "recovery"):
            ctx.pop(key, None)

        # Clear accumulated errors from previous cycle — keep only original
        # meaningful errors, drop infrastructure noise and monitor alerts
        ctx["errors"] = [
            e for e in ctx["errors"]
            if not e.startswith("[Monitor]")
            and "LedgerAgent" not in e
        ]

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

    # ── Emit pipeline completed event ─────────────────────────────────────
    emit_event(
        ctx,
        "pipeline_status",
        {
            "status": "completed",
            "state": ctx.get("state"),
            "intents": ctx.get("intents", [ctx.get("intent")]),
            "priority": ctx.get("priority", "n/a"),
            "risk_level": ctx.get("risk", {}).get("level", "n/a"),
        },
        agent="Orchestrator",
        step="pipeline",
        message="Pipeline execution completed",
    )

    return _build_result(ctx)


def _run_plan(ctx: dict[str, Any], plan: list[dict]) -> dict[str, Any]:
    """Execute the planner-generated main pipeline steps."""
    for step in plan:
        agent_key   = step["agent"]
        is_critical = step.get("critical", True)
        _emit_pipeline_step_event(ctx, agent_key, "started")

        try:
            agent = get_agent(agent_key)
        except KeyError as exc:
            msg = f"Orchestrator: {exc}"
            logger.error(msg)
            add_error(ctx, msg)
            log_step(ctx, agent_key, "skipped",
                     detail=f"Agent not found in registry: {agent_key}")
            _emit_pipeline_event(
                ctx,
                "error_occurred",
                {
                    "step": agent_key,
                    "message": msg,
                    "critical": is_critical,
                },
                agent="Orchestrator",
                step=agent_key,
                message=msg,
                log_text=f"[Orchestrator] {msg}",
                status="error",
            )
            if is_critical:
                update_context(ctx, state="failed")
                break
            continue

        try:
            ctx = agent.run(ctx)
            _emit_pipeline_step_event(ctx, agent_key, "completed")
            _emit_step_success(ctx, agent_key)
        except Exception as exc:
            logger.error("Orchestrator: %s raised %s", agent_key, exc)
            _emit_pipeline_step_event(ctx, agent_key, "failed", str(exc))
            _emit_pipeline_event(
                ctx,
                "error_occurred",
                {
                    "step": agent_key,
                    "message": str(exc),
                    "critical": is_critical,
                },
                agent=getattr(agent, "name", agent_key),
                step=agent_key,
                message=str(exc),
                log_text=f"[{getattr(agent, 'name', agent_key)}] {exc}",
                status="error",
            )
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
        _emit_pipeline_step_event(ctx, agent_key, "started")
        try:
            agent = get_agent(agent_key)
        except KeyError:
            logger.warning("[Autonomy] agent '%s' not in registry — skipping", agent_key)
            continue
        try:
            ctx = agent.run(ctx)
            _emit_pipeline_step_event(ctx, agent_key, "completed")
            if agent_key == "recovery":
                recovery = ctx.get("recovery", {}) or {}
                recovery_event = "recovery_success" if recovery.get("success") else "recovery_triggered"
                _emit_pipeline_event(
                    ctx,
                    recovery_event,
                    recovery or {"action": "none"},
                    agent=getattr(agent, "name", agent_key),
                    step=agent_key,
                    message=recovery.get("details") or "Recovery step completed",
                    log_text=f"[{getattr(agent, 'name', agent_key)}] {recovery.get('details', 'Recovery step completed')}",
                )
        except Exception as exc:
            logger.error("[Autonomy] '%s' raised %s — continuing", agent_key, exc)
            add_error(ctx, f"[Autonomy] {agent_key} failed: {exc}")
            _emit_pipeline_step_event(ctx, agent_key, "failed", str(exc))
            _emit_pipeline_event(
                ctx,
                "error_occurred",
                {
                    "step": agent_key,
                    "message": str(exc),
                    "critical": False,
                },
                agent=getattr(agent, "name", agent_key),
                step=agent_key,
                message=str(exc),
                log_text=f"[{getattr(agent, 'name', agent_key)}] {exc}",
                status="error",
            )
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

    # Only count errors that are not pure autonomy-internal noise or
    # non-critical infrastructure failures (Sheets, Excel sync, etc.)
    _INFRA_PREFIXES = ("[Autonomy]", "LedgerAgent:", "LedgerAgent ")
    meaningful_errors = [
        e for e in ctx.get("errors", [])
        if not any(e.startswith(prefix) or prefix.rstrip() in e
                   for prefix in _INFRA_PREFIXES)
    ]
    if meaningful_errors:
        logger.info(
            "[Feedback] replan trigger: %d meaningful error(s)", len(meaningful_errors)
        )
        return True

    return False


def _build_result(ctx: dict[str, Any]) -> dict[str, Any]:
    """Flatten context into the public API response shape."""
    # Remove internal keys that are not serialisable and must not leak
    # into the API response or the context dict returned to callers.
    ctx.pop("_step_callback", None)

    event = ctx.get("event", {}) or {}
    data = ctx.get("data", {}) or {}
    event_order = event.get("order", {}) if isinstance(event.get("order"), dict) else {}
    risk = ctx.get("risk", {}) or {}
    source = ctx.get("source", "system")

    payment_state = ctx.get("payment") or {}

    amount = payment_state.get("amount", event.get("amount"))
    if amount is None:
        amount = data.get("amount", 0)

    try:
        numeric_amount = float(amount or 0)
    except (TypeError, ValueError):
        numeric_amount = 0

    return {
        # ── Core (backward compatible) ────────────────────────────────────
        "message":       ctx["message"],
        "intent":        ctx.get("intent") or "other",
        "intents":       ctx.get("intents") or [ctx.get("intent") or "other"],
        "data":          ctx.get("data", {}),
        "multi_data":    ctx.get("multi_data", {}),
        "event":         ctx.get("event", {}),
        "invoice":       ctx.get("invoice"),
        "events":        ctx.get("events", []),
        "live_logs":     ctx.get("live_logs", []),
        "history":       ctx.get("history", []),
        "sheet_updated": ctx.get("metadata", {}).get("sheet_updated", False),
        "customer":      {"name": event.get("customer") or data.get("customer") or "Walk-in customer"},
        "order": {
            "item": event.get("item") or event_order.get("item") or data.get("item"),
            "quantity": event.get("quantity") or event_order.get("quantity") or data.get("quantity"),
            "status": event.get("status") or "received",
            "source": source,
        },
        "payment": {
            "invoice_id": payment_state.get("invoice_id") or (ctx.get("invoice") or {}).get("invoice_id") or event.get("invoice_id") or data.get("invoice_id"),
            "amount": payment_state.get("amount") or (ctx.get("invoice") or {}).get("total") or numeric_amount,
            "status": payment_state.get("status") or (ctx.get("invoice") or {}).get("status") or ("paid" if numeric_amount > 0 else "pending"),
        },
        "decision": {
            "intent": ctx.get("intent") or "other",
            "priority": ctx.get("priority", "low"),
            "priority_score": ctx.get("priority_score", 0),
            "risk": risk.get("level"),
        },
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


def _emit_step_success(ctx: dict[str, Any], agent_key: str) -> None:
    # ─── Emit phone notifications for business-relevant agents ─────────
    if agent_key == "invoice_agent":
        event_type = "invoice_generated"
        agent_name = "InvoiceAgent"
        payload = _build_step_payload(ctx, agent_key)
        message, log_text = _build_step_messages(ctx, agent_key, agent_name)
        _emit_pipeline_event(
            ctx,
            event_type,
            payload,
            agent=agent_name,
            step=agent_key,
            message=message,
            log_text=log_text,
        )
        
        # Emit notification
        invoice = payload.get("invoice") or {}
        invoice_id = invoice.get("invoice_id") or "N/A"
        total = invoice.get("total") or invoice.get("total_amount") or 0
        emit_notification(
            ctx,
            category="invoice",
            title="🧾 Invoice Created",
            message=f"{invoice_id} • ₹{total:,}",
            priority="normal",
            invoice_id=invoice_id,
            amount=total,
        )
        return
    
    if agent_key == "payment_agent":
        event_type = "payment_requested"
        agent_name = "PaymentAgent"
        payload = _build_step_payload(ctx, agent_key)
        message, log_text = _build_step_messages(ctx, agent_key, agent_name)
        _emit_pipeline_event(
            ctx,
            event_type,
            payload,
            agent=agent_name,
            step=agent_key,
            message=message,
            log_text=log_text,
        )
        
        # Emit notification
        payment = payload.get("payment") or {}
        invoice = payload.get("invoice") or {}
        invoice_id = payment.get("invoice_id") or invoice.get("invoice_id") or "N/A"
        amount = payment.get("amount") or invoice.get("total") or invoice.get("total_amount") or 0
        emit_notification(
            ctx,
            category="payment",
            title="💳 Payment Requested",
            message=f"{invoice_id} • ₹{amount:,}",
            priority="normal",
            invoice_id=invoice_id,
            amount=amount,
        )
        return
    
    # ─── Other agents ──────────────────────────────────────────────────
    event_type, agent_name = _STEP_EVENT_MAP.get(agent_key, ("execution_done", agent_key))
    payload = _build_step_payload(ctx, agent_key)
    message, log_text = _build_step_messages(ctx, agent_key, agent_name)
    _emit_pipeline_event(
        ctx,
        event_type,
        payload,
        agent=agent_name,
        step=agent_key,
        message=message,
        log_text=log_text,
    )

def _build_step_payload(ctx: dict[str, Any], agent_key: str) -> dict[str, Any]:
    if agent_key == "intent":
        return {
            "intent": ctx.get("intent") or "other",
            "intents": ctx.get("intents", []),
            "model_used": ctx.get("model_used"),
        }
    if agent_key == "extraction":
        return {
            "intent": ctx.get("intent") or "other",
            "data": ctx.get("data", {}),
            "multi_data": ctx.get("multi_data", {}),
        }
    if agent_key == "validation":
        return {
            "intent": ctx.get("intent") or "other",
            "data": ctx.get("data", {}),
        }
    if agent_key == "invoice_agent":
        return {
            "intent": ctx.get("intent") or "other",
            "invoice": ctx.get("invoice"),
        }
    if agent_key == "payment_agent":
        return {
            "intent": ctx.get("intent") or "other",
            "payment": ctx.get("payment"),
            "invoice": ctx.get("invoice"),
        }
    if agent_key == "ledger":
        return {
            "sheet_updated": ctx.get("metadata", {}).get("sheet_updated", False),
            "event": ctx.get("event", {}),
        }
    if agent_key == "recovery":
        return ctx.get("recovery", {})
    return {
        "state": ctx.get("state"),
        "event": ctx.get("event", {}),
    }


def _build_step_messages(ctx: dict[str, Any], agent_key: str, agent_name: str) -> tuple[str, str]:
    if agent_key == "intent":
        intent = ctx.get("intent") or "other"
        return (
            f"Intent detected: {intent}",
            f"[{agent_name}] Intent detected: {intent}",
        )
    if agent_key == "extraction":
        data = ctx.get("data", {}) or {}
        detail_parts = [f"{key}={value}" for key, value in data.items() if value not in (None, "", [], {})]
        detail = ", ".join(detail_parts) or "no structured fields extracted"
        return (
            f"Extraction completed: {detail}",
            f"[{agent_name}] Extracted: {detail}",
        )
    if agent_key == "validation":
        data = ctx.get("data", {}) or {}
        detail_parts = [f"{key}={value}" for key, value in data.items() if value not in (None, "", [], {})]
        detail = ", ".join(detail_parts) or "validation passed with empty payload"
        return (
            f"Validation completed: {detail}",
            f"[{agent_name}] Validated: {detail}",
        )
    if agent_key == "invoice_agent":
        invoice_id = (ctx.get("invoice") or {}).get("invoice_id") or "unknown"
        return (
            f"Invoice generated: {invoice_id}",
            f"[{agent_name}] Invoice generated: {invoice_id}",
        )
    if agent_key == "payment_agent":
        invoice_id = (ctx.get("payment") or {}).get("invoice_id") or (ctx.get("invoice") or {}).get("invoice_id") or "unknown"
        amount = (ctx.get("payment") or {}).get("amount", 0)
        return (
            f"Payment requested: {invoice_id}",
            f"[{agent_name}] Payment requested: {invoice_id} amount={amount}",
        )
    if agent_key == "ledger":
        updated = ctx.get("metadata", {}).get("sheet_updated", False)
        return (
            f"Execution completed: sheet_updated={updated}",
            f"[{agent_name}] Ledger update status: {updated}",
        )
    recovery = (ctx.get("recovery", {}) or {}).get("details") or "Recovery step completed"
    return (recovery, f"[{agent_name}] {recovery}")


def _emit_pipeline_event(
    ctx: dict[str, Any],
    event_type: str,
    payload: dict[str, Any],
    *,
    agent: str,
    step: str,
    message: str,
    log_text: str,
    status: str = "success",
) -> None:
    log_entry = push_live_log(
        ctx,
        {
            "agent": agent,
            "status": status,
            "action": message,
            "detail": log_text,
        },
    )
    emit_event(
        ctx,
        "log",
        {
            "step": step,
            "message": log_text,
        },
        agent=agent,
        step=step,
        message=log_text,
        log_entry=log_entry,
    )
    emit_event(
        ctx,
        event_type,
        payload,
        agent=agent,
        step=step,
        message=message,
        log_entry=log_entry,
    )


def _emit_pipeline_step_event(
    ctx: dict[str, Any],
    step: str,
    status: str,
    detail: str = "",
) -> None:
    step_message = f"{step} {status}"
    log_entry = push_live_log(
        ctx,
        {
            "agent": "Orchestrator",
            "status": "error" if status == "failed" else "info",
            "action": step_message,
            "detail": detail or f"[Orchestrator] Step {step} {status}",
        },
    )

    # Emit log event immediately - real-time feedback
    emit_event(
        ctx,
        "log",
        {
            "step": step,
            "status": status,
            "message": detail or step_message,
        },
        agent="Orchestrator",
        step=step,
        message=detail or step_message,
        log_entry=log_entry,
    )

    # Emit pipeline step event immediately - real-time feedback
    event = emit_event(
        ctx,
        "pipeline_step",
        {
            "step": step,
            "status": status,
            "detail": detail,
        },
        agent="Orchestrator",
        step=step,
        message=step_message,
        log_entry=log_entry,
    )

    # Per-step streaming hook — the API layer injects a callback via
    # ctx["_step_callback"](payload) that is thread-safe and non-blocking.
    # When running outside an HTTP request (CLI, tests) this key is absent
    # and we skip silently.
    cb = ctx.get("_step_callback")
    if cb is not None:
        try:
            cb({"type": "pipeline_step", "step": step, "status": status,
                "detail": detail, "event": event})
        except Exception:
            pass  # never let streaming errors affect the pipeline
