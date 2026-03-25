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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

from pydantic import BaseModel


class NotificationRequest(BaseModel):
    """Incoming notification payload."""
    source:  str = "system"   # e.g. "whatsapp", "amazon", "payment", "return"
    message: str              # Raw Hinglish business message


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
# Internal: run the pipeline and build the API response dict
# ---------------------------------------------------------------------------

def _run_pipeline(message: str, source: str) -> dict[str, Any]:
    """
    Run the full multi-agent pipeline via process_message() and return
    a flat API response dict that includes both legacy and new fields.
    """
    from app.core.orchestrator import process_message

    result = process_message(message.strip(), source=source)

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


# ---------------------------------------------------------------------------
# POST /api/notification
# ---------------------------------------------------------------------------

@router.post("/api/notification")
async def process_notification(body: NotificationRequest):
    """
    Receive a business notification and run the full Notiflow pipeline.

    Uses process_message() from app.core.orchestrator — the new multi-agent
    system with dynamic planner, autonomy planner, and multi-intent support.

    After processing, the result is broadcast to all connected WebSocket
    clients so the live stream panel updates in real time.

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

    try:
        response = _run_pipeline(body.message.strip(), body.source)
    except Exception as exc:
        logger.error("Pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}")

    # Broadcast full result to WebSocket clients
    await _manager.broadcast(response)

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

                response = _run_pipeline(message, source)
                await _manager.broadcast(response)

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