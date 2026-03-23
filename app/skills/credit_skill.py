"""
credit_skill.py
---------------
Business Skill: Credit / Udhar  (Stage 6 — with persistence)

Handles the "credit" intent.
Appends a credit entry to the Ledger sheet.

Expected input fields:
    customer  (str | None)
    item      (str | None)
    quantity  (int | None)
    amount    (int | None)
"""

import logging
from datetime import datetime, timezone

from app.utils.excel_writer import append_row, read_sheet

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_entry_id(prefix: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    df    = read_sheet("Ledger")
    seq   = len(df) + 1
    return f"{prefix}-{today}-{seq:04d}"


def process_credit(data: dict) -> dict:
    """
    Process a credit (udhar) event and append it to the Ledger sheet.

    Args:
        data: Extracted fields dict. Expected keys: customer, item, quantity, amount

    Returns:
        {
            "event":  "credit_recorded",
            "credit": { ledger entry }
        }
    """
    logger.info("CreditSkill processing: %s", data)

    entry_id = _generate_entry_id("CRD")

    credit = {
        "entry_id":     entry_id,
        "timestamp":    _now_iso(),
        "type":         "credit",
        "customer":     data.get("customer"),
        "item":         data.get("item"),
        "quantity":     data.get("quantity"),
        "amount":       data.get("amount"),
        "payment_type": None,
        "status":       "open",
    }

    append_row("Ledger", credit)

    return {
        "event":  "credit_recorded",
        "credit": credit,
    }