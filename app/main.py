"""
app/main.py
-----------
Primary entry point for NotiFlow Autonomous.

Public API (UNCHANGED — backward compatible):
    run_notiflow(message, demo_mode, source) -> dict

Changes from original:
    - Live mode now calls app.core.orchestrator.process_message()
      instead of agent.orchestrator.process_message()
    - Demo mode is unchanged (same static responses + keyword fallback)
    - Bedrock references removed entirely
    - Context is created here in live mode and flows through pipeline

CLI usage (unchanged):
    python app/main.py "rahul ne 15000 bheja"
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from app.config import DEMO_MODE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demo pipeline (no cloud credentials needed)
# ---------------------------------------------------------------------------

_DEMO_RESPONSES: dict[str, dict] = {
    "rahul ne 15000 bheja": {
        "intent": "payment",
        "data":   {"customer": "Rahul", "amount": 15000, "payment_type": None},
        "event":  {"event": "payment_recorded",
                   "payment": {"customer": "Rahul", "amount": 15000,
                               "payment_type": None, "status": "received"}},
    },
    "bhaiya 3 kurti bhej dena": {
        "intent": "order",
        "data":   {"customer": None, "item": "kurti", "quantity": 3},
        "event":  {"event": "order_received",
                   "order":  {"customer": None, "item": "kurti",
                              "quantity": 3, "status": "pending"},
                   "invoice": {"invoice_id": "INV-DEMO-0001", "total_amount": 0.0}},
    },
    "priya ke liye 2 kilo aata bhej dena": {
        "intent": "order",
        "data":   {"customer": "Priya", "item": "aata", "quantity": 2},
        "event":  {"event": "order_received",
                   "order":  {"customer": "Priya", "item": "aata",
                              "quantity": 2, "status": "pending"},
                   "invoice": {"invoice_id": "INV-DEMO-0002", "total_amount": 0.0}},
    },
    "size chota hai exchange karna hai": {
        "intent": "return",
        "data":   {"customer": None, "item": None, "reason": "size issue"},
        "event":  {"event": "return_requested",
                   "return": {"customer": None, "item": None,
                              "reason": "size issue", "status": "pending_review"}},
    },
    "udhar me de dijiye": {
        "intent": "credit",
        "data":   {"customer": None, "item": None, "quantity": None, "amount": None},
        "event":  {"event": "credit_recorded",
                   "credit": {"customer": None, "amount": None, "status": "open"}},
    },
    "suresh ko 500 ka maal udhar dena": {
        "intent": "credit",
        "data":   {"customer": "Suresh", "item": "goods", "quantity": None, "amount": 500},
        "event":  {"event": "credit_recorded",
                   "credit": {"customer": "Suresh", "amount": 500, "status": "open"}},
    },
    "3 kurti ka set ready rakhna": {
        "intent": "preparation",
        "data":   {"item": "kurti", "quantity": 3},
        "event":  {"event": "preparation_queued",
                   "preparation": {"item": "kurti", "quantity": 3, "status": "queued"}},
    },
    "amit bhai ka 8000 gpay se aaya": {
        "intent": "payment",
        "data":   {"customer": "Amit", "amount": 8000, "payment_type": "upi"},
        "event":  {"event": "payment_recorded",
                   "payment": {"customer": "Amit", "amount": 8000,
                               "payment_type": "upi", "status": "received"}},
    },
}


def _fallback_intent(message: str) -> str:
    m = message.lower()
    if any(w in m for w in ["bheja", "aaya", "cash", "gpay", "upi", "paytm", "online"]):
        return "payment"
    if any(w in m for w in ["exchange", "wapas", "return", "vapas", "size"]):
        return "return"
    if any(w in m for w in ["udhar", "credit", "baad"]):
        return "credit"
    if any(w in m for w in ["ready", "pack", "rakhna", "taiyar"]):
        return "preparation"
    if any(w in m for w in ["bhej", "dena", "chahiye", "kilo", "piece"]):
        return "order"
    return "other"


def _run_demo(message: str, source: str = "system") -> dict[str, Any]:
    key      = message.strip().lower()
    response = _DEMO_RESPONSES.get(key)
    if response is None:
        intent   = _fallback_intent(message)
        response = {
            "intent": intent,
            "data":   {"note": f"Demo: classified as '{intent}'"},
            "event":  {"event": f"{intent}_recorded",
                       "note":  "Demo fallback — no exact match"},
        }

    from app.services.google_sheets_service import append_transaction
    sheet_updated = append_transaction(
        intent=response["intent"],
        data=response["data"],
        source=source,
    )

    return {
        "message":       message,
        "intent":        response["intent"],
        "data":          response["data"],
        "event":         response["event"],
        "sheet_updated": sheet_updated,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_notiflow(
    message:   str,
    demo_mode: bool | None = None,
    source:    str = "system",
) -> dict[str, Any]:
    """
    Run a business message through the full NotiFlow pipeline.

    Args:
        message:   Raw Hinglish or English business message.
        demo_mode: Override DEMO_MODE from config. None = use config value.
        source:    Notification source (e.g. "whatsapp", "gpay").

    Returns:
        {
            "message":       str,
            "intent":        str,
            "data":          dict,
            "event":         dict,
            "sheet_updated": bool,
        }
    """
    if not message or not message.strip():
        raise ValueError("Message cannot be empty.")

    use_demo = DEMO_MODE if demo_mode is None else demo_mode

    if use_demo:
        logger.info("run_notiflow [demo] ← %r", message)
        return _run_demo(message.strip(), source=source)
    else:
        logger.info("run_notiflow [live] ← %r", message)
        # ── NEW: use context-driven orchestrator ─────────────────────────────
        from app.core.orchestrator import process_message
        return process_message(message.strip(), source=source)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    if len(sys.argv) < 2:
        print('Usage: python app/main.py "<business message>"')
        sys.exit(1)

    input_message = " ".join(sys.argv[1:])
    try:
        result = run_notiflow(input_message)
        # Strip context from CLI output to keep it readable
        result.pop("context", None)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(1)
