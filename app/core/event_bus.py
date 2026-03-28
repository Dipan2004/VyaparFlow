from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

_LOG_BUFFER: deque[dict[str, Any]] = deque(maxlen=500)
_EVENT_BUFFER: deque[dict[str, Any]] = deque(maxlen=200)
_INVOICE_STORE: dict[str, dict[str, Any]] = {}
_EVENT_SEQ = 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}-{stamp}"


def push_live_log(ctx: dict[str, Any] | None, entry: dict[str, Any]) -> dict[str, Any]:
    log_entry = {
        "id": entry.get("id") or _make_id("log"),
        "agent": entry.get("agent", "System"),
        "status": entry.get("status", "info"),
        "detail": entry.get("detail", ""),
        "action": entry.get("action", ""),
        "timestamp": entry.get("timestamp") or _now_iso(),
    }
    if ctx is not None:
        ctx.setdefault("live_logs", []).append(log_entry)
    _LOG_BUFFER.append(log_entry)
    return log_entry


def get_logs(limit: int | None = None) -> list[dict[str, Any]]:
    logs = list(_LOG_BUFFER)
    if limit is not None:
        logs = logs[-limit:]
    return logs


def emit_event(
    ctx: dict[str, Any] | None,
    event_type: str,
    payload: dict[str, Any],
    *,
    agent: str | None = None,
    step: str | None = None,
    message: str | None = None,
    log_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    global _EVENT_SEQ
    _EVENT_SEQ += 1
    event_id = _make_id("evt")
    event = {
        "id": event_id,
        "event_id": event_id,
        "sequence": _EVENT_SEQ,
        "sequence_number": _EVENT_SEQ,
        "type": event_type,
        "timestamp": _now_iso(),
        "agent": agent,
        "step": step or event_type,
        "message": message or "",
        "data": deepcopy(payload),
        "payload": deepcopy(payload),
        "log": deepcopy(log_entry) if log_entry else None,
    }
    if ctx is not None:
        ctx.setdefault("events", []).append(event)
    _EVENT_BUFFER.append(event)

    invoice_id = payload.get("invoice_id") or payload.get("id")
    if invoice_id and isinstance(payload.get("items"), list):
        store_invoice(payload)

    return event


def emit_global_event(event_type: str, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return emit_event(None, event_type, payload, **kwargs)


def get_events(limit: int | None = None) -> list[dict[str, Any]]:
    events = list(_EVENT_BUFFER)
    if limit is not None:
        events = events[-limit:]
    return events


def get_events_since(sequence: int) -> list[dict[str, Any]]:
    return [event for event in _EVENT_BUFFER if int(event.get("sequence", 0)) > sequence]


def get_latest_event_sequence() -> int:
    if not _EVENT_BUFFER:
        return 0
    return int(_EVENT_BUFFER[-1].get("sequence", 0))


def store_invoice(invoice: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(invoice)
    invoice_id = normalized.get("invoice_id") or normalized.get("id")
    if not invoice_id:
        return normalized
    normalized["invoice_id"] = invoice_id
    normalized["id"] = invoice_id
    _INVOICE_STORE[invoice_id] = normalized
    return normalized


def get_invoice(invoice_id: str) -> dict[str, Any] | None:
    invoice = _INVOICE_STORE.get(invoice_id)
    return deepcopy(invoice) if invoice else None


def confirm_invoice_payment(invoice_id: str) -> dict[str, Any] | None:
    invoice = _INVOICE_STORE.get(invoice_id)
    if not invoice:
        return None
    invoice["status"] = "paid"
    return store_invoice(invoice)
