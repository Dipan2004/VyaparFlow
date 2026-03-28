"""
api/notification_routes.py
--------------------------
FastAPI router for Notiflow notification endpoints.

Phase 5: API now calls process_message() directly (the new multi-agent
orchestrator) instead of run_notiflow(). Returns the full result including
intents, multi_data, priority, risk, and alerts.

Backward compatibility: all original fields (message, intent, data, event,
source, sheet_updated, model) are still present in the response.

Endpoints
---------
POST /api/notification
    Receives a notification, runs the full agent pipeline,
    returns the structured orchestrator result.

GET  /api/notifications/generate
    Calls Gemini to generate a batch of demo notifications.
    Query param: n (default 5)

WebSocket /ws/notifications
    Streams live notifications to connected clients.
    Accepts both frontend-pushed and Gemini-generated events.
    Broadcasts to all connected clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.core.event_bus import (
    confirm_invoice_payment,
    emit_global_event,
    get_events_since,
    get_latest_event_sequence,
    get_logs,
    push_live_log,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Startup safety check
# ---------------------------------------------------------------------------

def _warn_if_demo_mode() -> None:
    """Log a loud warning when demo mode is active so operators notice it."""
    from app.config import DEMO_MODE
    if DEMO_MODE:
        logger.warning(
            "⚠️  DEMO MODE IS ACTIVE — no LLM calls will be made and the live "
            "pipeline will NOT execute.  Set NOTIFLOW_DEMO_MODE=false in your "
            ".env file before deploying to production."
        )

_warn_if_demo_mode()


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

from pydantic import BaseModel


class NotificationRequest(BaseModel):
    """Incoming notification payload."""
    source:  str = "system"   # e.g. "whatsapp", "amazon", "payment", "return"
    message: str              # Raw Hinglish business message


class PaymentConfirmRequest(BaseModel):
    invoice_id: str


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class _ConnectionManager:
    """Simple in-memory broadcast manager for WebSocket clients."""

    def __init__(self):
        self._active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.append(ws)
        logger.info("WS client connected. Total: %d", len(self._active))

    def disconnect(self, ws: WebSocket) -> None:
        self._active = [c for c in self._active if c is not ws]
        logger.info("WS client disconnected. Total: %d", len(self._active))

    async def broadcast(self, payload: dict) -> None:
        """Send JSON payload to all connected WebSocket clients."""
        dead = []
        for ws in self._active:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


_manager = _ConnectionManager()


# ---------------------------------------------------------------------------
# Per-step streaming support
# ---------------------------------------------------------------------------

import queue as _queue_module


def _run_pipeline(
    message: str,
    source: str,
    step_queue: "_queue_module.Queue | None" = None,
) -> dict[str, Any]:
    """
    Run the full multi-agent pipeline via process_message() and return
    a flat API response dict that includes both legacy and new fields.

    If step_queue is provided, each pipeline step emits a dict into it
    so the caller can stream incremental updates to connected clients
    before the final result is ready.
    """
    from app.core.orchestrator import process_message

    # Build the step callback that the orchestrator will call after each step.
    # It is thread-safe (queue.put is GIL-safe) and never raises.
    step_cb = None
    if step_queue is not None:
        def step_cb(payload: dict) -> None:  # noqa: E306
            try:
                step_queue.put_nowait(payload)
            except Exception:
                pass

    result = process_message(
        message.strip(),
        source=source,
        step_callback=step_cb,
    )

    # Strip the raw context from the response (keep it lightweight for API)
    ctx = result.pop("context", {})

    # Determine model tag
    event_str  = str(result.get("event", {}).get("event", ""))
    is_live    = any(event_str.endswith(sfx)
                     for sfx in ("_recorded", "_received", "_requested", "_queued"))
    model_tag  = "live" if is_live else "demo"

    return {
        # ── Backward-compatible core fields ──────────────────────────────
        "message":       result["message"],
        "intent":        result.get("intent", "other"),
        "data":          result.get("data", {}),
        "event":         result.get("event", {}),
        "invoice":       result.get("invoice"),
        "events":        result.get("events", []),
        "live_logs":     result.get("live_logs", []),
        "history":       result.get("history", ctx.get("history", [])),
        "customer":      result.get("customer", {}),
        "order":         result.get("order", {}),
        "payment":       result.get("payment", {}),
        "decision":      result.get("decision", {}),
        "source":        source,
        "sheet_updated": result.get("sheet_updated", False),
        "model":         model_tag,
        # ── Phase 5: multi-intent fields ─────────────────────────────────
        "intents":       result.get("intents", [result.get("intent", "other")]),
        "multi_data":    result.get("multi_data", {}),
        # ── Autonomy fields ───────────────────────────────────────────────
        "priority":      result.get("priority", "low"),
        "priority_score": result.get("priority_score", 0),
        "risk":          result.get("risk", {}),
        "alerts":        result.get("alerts", []),
        "verification":  result.get("verification", {}),
        "recovery":      result.get("recovery", {}),
        "monitor":       result.get("monitor", {}),
    }


async def _broadcast_pipeline_response(response: dict[str, Any]) -> None:
    await _manager.broadcast({"type": "pipeline_result", "data": response})
    for event in response.get("events", []):
        await _manager.broadcast({"type": "domain_event", "event": event})


async def _drain_step_queue(q: "_queue_module.Queue") -> None:
    """
    Drain pipeline step events from a thread-safe queue and broadcast them
    to all connected WebSocket clients.  Runs concurrently with the pipeline
    executor so the frontend receives incremental updates in real time.
    Terminates automatically when a sentinel None value is received.
    """
    while True:
        try:
            payload = q.get_nowait()
        except _queue_module.Empty:
            await asyncio.sleep(0.05)
            continue
        if payload is None:          # sentinel: pipeline finished
            break
        try:
            await _manager.broadcast(payload)
        except Exception:
            pass  # never let broadcast errors kill the drain loop


# ---------------------------------------------------------------------------
# POST /api/notification
# ---------------------------------------------------------------------------

@router.post("/api/notification")
async def process_notification(body: NotificationRequest):
    """
    Receive a business notification and run the full Notiflow pipeline.

    Uses process_message() from app.core.orchestrator — the new multi-agent
    system with dynamic planner, autonomy planner, and multi-intent support.

    Streams per-step pipeline events to all connected WebSocket clients while
    the pipeline is still running, then broadcasts the final result.

    Args:
        body: {"source": "whatsapp", "message": "bhaiya 3 kurti bhej dena"}

    Returns:
        Full orchestrator result including intents, multi_data, priority, risk.
    """
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    logger.info(
        "POST /api/notification | source=%s | msg=%r",
        body.source, body.message
    )
    print("🔥 RECEIVED MESSAGE:", body.message)

    # Create a thread-safe queue so the executor thread can push incremental
    # step events that the async drain task forwards to WebSocket clients.
    step_q: _queue_module.Queue = _queue_module.Queue()
    drain_task = asyncio.create_task(_drain_step_queue(step_q))

    try:
        # Run the synchronous (blocking) pipeline in a thread-pool executor so
        # it does not block the async event loop during LLM HTTP calls.
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, _run_pipeline, body.message.strip(), body.source, step_q
        )
    except Exception as exc:
        logger.error("Pipeline error: %s", exc)
        step_q.put_nowait(None)       # unblock the drain task
        await drain_task
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}")

    # Signal the drain task that the pipeline is finished, then wait for it
    # to flush any remaining queued events before we broadcast the final result.
    step_q.put_nowait(None)
    await drain_task

    # Broadcast full result to WebSocket clients
    await _broadcast_pipeline_response(response)

    return response


@router.get("/api/stream/logs")
async def stream_logs(limit: int = Query(default=200, ge=1, le=500)):
    return {"logs": get_logs(limit)}


@router.get("/api/stream/events")
async def stream_events(request: Request):
    async def event_generator():
        last_sequence = max(0, get_latest_event_sequence() - 20)
        while True:
            if await request.is_disconnected():
                break

            events = get_events_since(last_sequence)
            for event in events:
                last_sequence = max(last_sequence, int(event.get("sequence", 0)))
                yield f"data: {json.dumps(event)}\n\n"

            await asyncio.sleep(0.25)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/api/payment/confirm")
async def confirm_payment(body: PaymentConfirmRequest):
    invoice_id = body.invoice_id.strip()
    if not invoice_id:
        raise HTTPException(status_code=422, detail="invoice_id is required")

    from app.utils.excel_writer import append_row

    invoice = confirm_invoice_payment(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail=f"Invoice not found: {invoice_id}")

    payment_entry = {
        "entry_id": f"PAY-{invoice_id}",
        "timestamp": invoice.get("timestamp"),
        "type": "payment",
        "customer": invoice.get("customer"),
        "item": invoice.get("item"),
        "quantity": invoice.get("quantity"),
        "amount": invoice.get("total") or invoice.get("total_amount"),
        "payment_type": "manual",
        "status": "received",
    }
    append_row("Ledger", payment_entry)

    payment_log = push_live_log(None, {
        "agent": "PaymentAPI",
        "status": "success",
        "action": f"Payment confirmed for {invoice_id}",
        "detail": f"[PaymentAPI] Payment confirmed: {invoice_id}",
    })
    event = emit_global_event(
        "payment_completed",
        invoice,
        agent="PaymentAPI",
        step="payment",
        message=f"Payment confirmed for {invoice_id}",
        log_entry=payment_log,
    )

    response = {
        "invoice": invoice,
        "payment": {
            "invoice_id": invoice.get("invoice_id"),
            "amount": invoice.get("total") or invoice.get("total_amount"),
            "status": "paid",
        },
        "event": event,
    }
    await _manager.broadcast({"type": "domain_event", "event": event})
    return response


# ---------------------------------------------------------------------------
# GET /api/notifications/generate
# ---------------------------------------------------------------------------

@router.get("/api/notifications/generate")
async def generate_demo_notifications(n: int = Query(default=5, ge=1, le=20)):
    """
    Generate n demo notifications using Gemini (or static fallback).

    Query params:
        n: number of notifications to generate (1-20, default 5)

    Returns:
        {"notifications": [{"source": str, "message": str}, ...]}
    """
    from app.services.notification_generator import get_notifications
    notifications = get_notifications(n)
    return {"notifications": notifications}


# ---------------------------------------------------------------------------
# WebSocket /ws/notifications
# ---------------------------------------------------------------------------

@router.websocket("/ws/notifications")
async def websocket_notification_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time notification streaming.

    Clients connect and receive:
      - Notifications pushed by the frontend simulation
      - Notifications generated by Gemini automation
      - Results of processed notifications (broadcast from POST endpoint)

    The client can also SEND a notification over the WebSocket:
        {"source": "whatsapp", "message": "bhaiya 3 kurti bhej dena"}

    The server will process it through the pipeline and broadcast the
    result to all connected clients.

    Protocol:
        Client → Server:  {"source": str, "message": str}
        Server → Client:  Full pipeline result JSON (same shape as POST response)
    """
    await _manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
                source  = payload.get("source", "websocket")
                message = payload.get("message", "").strip()

                if not message:
                    await websocket.send_json({"error": "Empty message"})
                    continue

                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, _run_pipeline, message, source)
                await _broadcast_pipeline_response(response)

            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON payload"})
            except Exception as exc:
                logger.error("WS pipeline error: %s", exc)
                await websocket.send_json({"error": str(exc)})

    except WebSocketDisconnect:
        _manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# GET /api/stream/start
# ---------------------------------------------------------------------------

@router.get("/api/stream/start")
async def start_gemini_stream(
    n:     int   = Query(default=5,   ge=1,  le=20),
    delay: float = Query(default=2.0, ge=0.5, le=30.0),
):
    """
    Trigger Gemini to generate n notifications and stream them to all
    connected WebSocket clients with a delay between each.

    Query params:
        n:     number of notifications (default 5)
        delay: seconds between each broadcast (default 2.0)

    This runs in the background — the HTTP response returns immediately.
    """
    async def _stream():
        from app.services.notification_generator import stream_notifications
        async for notification in stream_notifications(n=n, delay_seconds=delay):
            await _manager.broadcast({
                "type":    "incoming_notification",
                "source":  notification["source"],
                "message": notification["message"],
            })

    asyncio.create_task(_stream())
    return {"status": "streaming started", "n": n, "delay_seconds": delay}