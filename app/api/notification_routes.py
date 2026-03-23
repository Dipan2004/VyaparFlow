"""
api/notification_routes.py
--------------------------
FastAPI router for Notiflow notification endpoints.

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
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class NotificationRequest(BaseModel):
    """Incoming notification payload."""
    source:  str          # e.g. "whatsapp", "amazon", "payment", "return"
    message: str          # Raw Hinglish business message


class NotificationResponse(BaseModel):
    """
    Full orchestrator result — same shape as run_notiflow() output.
    Frontend reads fields from data{} and event{}.
    """
    message: str
    intent:  str
    data:    dict[str, Any]
    event:   dict[str, Any]
    source:  str           # Echo back the notification source
    sheet_updated: bool = False   # Whether the Google Sheets ledger was updated
    model:   str | None = None   # "nova" | "gemini" | "demo"


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
# POST /api/notification
# ---------------------------------------------------------------------------

@router.post("/api/notification", response_model=NotificationResponse)
async def process_notification(body: NotificationRequest):
    """
    Receive a business notification and run the full Notiflow pipeline.

    The endpoint calls run_notiflow(message) from app/main.py — it does
    not call agents or skills directly.

    After processing, the result is broadcast to all connected WebSocket
    clients so the live stream panel updates in real time.

    Args:
        body: {"source": "whatsapp", "message": "bhaiya 3 kurti bhej dena"}

    Returns:
        Full orchestrator result + source echo.
    """
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    logger.info("POST /api/notification | source=%s | msg=%r", body.source, body.message)

    try:
        from app.main import run_notiflow
        result = run_notiflow(body.message.strip(), source=body.source)
    except Exception as exc:
        logger.error("Pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}")

    response = NotificationResponse(
        message = result["message"],
        intent  = result["intent"],
        data    = result["data"],
        event   = result["event"],
        source  = body.source,
        sheet_updated = result.get("sheet_updated", False),
        model   = "demo" if not result["event"].get("event", "").endswith("_recorded")
                         and not result["event"].get("event", "").endswith("_received")
                         and not result["event"].get("event", "").endswith("_requested")
                         and not result["event"].get("event", "").endswith("_queued")
                  else "live",
    )

    # Broadcast to WebSocket clients
    await _manager.broadcast(response.model_dump())

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
        Server → Client:  NotificationResponse JSON
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

                from app.main import run_notiflow
                result = run_notiflow(message, source=source)

                response = {
                    "message":       result["message"],
                    "intent":        result["intent"],
                    "data":          result["data"],
                    "event":         result["event"],
                    "source":        source,
                    "sheet_updated": result.get("sheet_updated", False),
                }
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