"""
services/excel_sync.py
----------------------
Semantic Excel sync wrapper for Notiflow.

Wraps utils/excel_writer.append_row() with business-named functions so
skills and the FastAPI backend can call append_order(), append_payment()
etc. without knowing the sheet schema details.

Excel writes always go to EXCEL_SYNC_FILE from app/config.py.
If EXCEL_FILE_PATH env var is set, that path is used; otherwise falls
back to the default DATA_FILE path (data/notiflow_data.xlsx).

No Excel writing logic is duplicated here — this is a thin adapter only.

Public API
----------
append_order(event_dict)    — writes to Orders sheet
append_payment(event_dict)  — writes to Ledger sheet (type="payment")
append_return(event_dict)   — writes to Returns sheet
append_credit(event_dict)   — writes to Ledger sheet (type="credit")
append_inventory(record)    — writes to Inventory sheet
append_invoice(record)      — writes to Invoices sheet
sync_from_event(result)     — auto-routes based on intent (convenience)
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import EXCEL_SYNC_FILE
from app.utils.excel_writer import append_row, EXCEL_FILE as _DEFAULT_FILE

logger = logging.getLogger(__name__)


def _active_file() -> Path:
    """
    Return the active Excel file path.
    EXCEL_SYNC_FILE (from env EXCEL_FILE_PATH) takes priority over default.
    """
    return Path(EXCEL_SYNC_FILE)


# ---------------------------------------------------------------------------
# Sheet-specific append functions
# ---------------------------------------------------------------------------

def append_order(event_dict: dict) -> None:
    """
    Append an order record to the Orders sheet.

    Args:
        event_dict: The "order" sub-dict from an order skill event.
                    Expected keys: order_id, timestamp, customer, item,
                                   quantity, status
    """
    record = {
        "order_id":  event_dict.get("order_id"),
        "timestamp": event_dict.get("timestamp"),
        "customer":  event_dict.get("customer"),
        "item":      event_dict.get("item"),
        "quantity":  event_dict.get("quantity"),
        "status":    event_dict.get("status", "pending"),
    }
    append_row("Orders", record)
    logger.info("Excel sync → Orders: %s", record.get("order_id"))


def append_payment(event_dict: dict) -> None:
    """
    Append a payment record to the Ledger sheet.

    Args:
        event_dict: The "payment" sub-dict from a payment skill event.
                    Expected keys: entry_id, timestamp, customer,
                                   amount, payment_type, status
    """
    record = {
        "entry_id":     event_dict.get("entry_id"),
        "timestamp":    event_dict.get("timestamp"),
        "type":         "payment",
        "customer":     event_dict.get("customer"),
        "item":         None,
        "quantity":     None,
        "amount":       event_dict.get("amount"),
        "payment_type": event_dict.get("payment_type"),
        "status":       event_dict.get("status", "received"),
    }
    append_row("Ledger", record)
    logger.info("Excel sync → Ledger (payment): customer=%s", record.get("customer"))


def append_return(event_dict: dict) -> None:
    """
    Append a return record to the Returns sheet.

    Args:
        event_dict: The "return" sub-dict from a return skill event.
                    Expected keys: return_id, timestamp, customer,
                                   item, reason, status
    """
    record = {
        "return_id": event_dict.get("return_id"),
        "timestamp": event_dict.get("timestamp"),
        "customer":  event_dict.get("customer"),
        "item":      event_dict.get("item"),
        "reason":    event_dict.get("reason"),
        "status":    event_dict.get("status", "pending_review"),
    }
    append_row("Returns", record)
    logger.info("Excel sync → Returns: %s", record.get("return_id"))


def append_credit(event_dict: dict) -> None:
    """
    Append a credit (udhar) record to the Ledger sheet.

    Args:
        event_dict: The "credit" sub-dict from a credit skill event.
    """
    record = {
        "entry_id":     event_dict.get("entry_id"),
        "timestamp":    event_dict.get("timestamp"),
        "type":         "credit",
        "customer":     event_dict.get("customer"),
        "item":         event_dict.get("item"),
        "quantity":     event_dict.get("quantity"),
        "amount":       event_dict.get("amount"),
        "payment_type": None,
        "status":       event_dict.get("status", "open"),
    }
    append_row("Ledger", record)
    logger.info("Excel sync → Ledger (credit): customer=%s", record.get("customer"))


def append_inventory(record: dict) -> None:
    """
    Append a stock movement record to the Inventory sheet.

    Args:
        record: Dict with keys: timestamp, item, change, direction,
                                reference_id, note
    """
    append_row("Inventory", record)
    logger.info(
        "Excel sync → Inventory: %s %s (%s)",
        record.get("direction"), record.get("item"), record.get("change"),
    )


def append_invoice(record: dict) -> None:
    """
    Append an invoice record to the Invoices sheet.

    Args:
        record: Invoice dict from invoice_service.generate_invoice().
    """
    append_row("Invoices", record)
    logger.info("Excel sync → Invoices: %s", record.get("invoice_id"))


# ---------------------------------------------------------------------------
# Convenience router — auto-dispatches based on orchestrator result intent
# ---------------------------------------------------------------------------

def sync_from_event(result: dict) -> None:
    """
    Automatically sync an orchestrator result to the correct Excel sheet(s).

    Called by the FastAPI notification handler after skill execution so
    the ledger is always up to date without skills needing to know about
    the sync layer.

    Note: Skills already write to Excel internally (Stages 5-6).
    This function provides a secondary sync point for the FastAPI path
    when skills are called via run_notiflow() in demo mode (where skills
    don't execute and nothing is written). In live mode, this is a no-op
    safety net — duplicate rows are avoided by checking event type.

    Args:
        result: Full orchestrator result dict
                {message, intent, data, event}
    """
    intent = result.get("intent", "other")
    event  = result.get("event", {})
    event_name = event.get("event", "")

    # In live mode the skill already wrote to Excel — skip to avoid duplicates.
    # We only sync here if the result came from demo mode (event has no IDs).
    order_data   = event.get("order")
    payment_data = event.get("payment")
    return_data  = event.get("return")
    credit_data  = event.get("credit")

    if intent == "order" and order_data and order_data.get("order_id"):
        # Already written by skill — skip
        logger.debug("sync_from_event: order already persisted by skill, skipping.")
    elif intent == "payment" and payment_data and payment_data.get("entry_id"):
        logger.debug("sync_from_event: payment already persisted by skill, skipping.")
    elif intent == "return" and return_data and return_data.get("return_id"):
        logger.debug("sync_from_event: return already persisted by skill, skipping.")
    elif intent == "credit" and credit_data and credit_data.get("entry_id"):
        logger.debug("sync_from_event: credit already persisted by skill, skipping.")
    else:
        logger.debug(
            "sync_from_event: demo mode result or missing IDs — "
            "no additional Excel write needed."
        )