"""
payment_skill.py
----------------
Business Skill: Payment  (Stage 6 — with persistence)

Handles the "payment" intent.
Appends a payment entry to the Ledger sheet.

Expected input fields:
    customer      (str | None)  — name of the person who sent money
    amount        (int | None)  — monetary amount
    payment_type  (str | None)  — "cash", "upi", "online", "cheque", or None
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


def process_payment(data: dict) -> dict:
    """
    Process a payment event and append it to the Ledger sheet.

    Args:
        data: Extracted fields dict. Expected keys: customer, amount, payment_type

    Returns:
        {
            "event":   "payment_recorded",
            "payment": { ledger entry }
        }
    """
    logger.info("PaymentSkill processing: %s", data)

    entry_id = _generate_entry_id("PAY")

    payment = {
        "entry_id":     entry_id,
        "timestamp":    _now_iso(),
        "type":         "payment",
        "customer":     data.get("customer"),
        "item":         None,
        "quantity":     None,
        "amount":       data.get("amount"),
        "payment_type": data.get("payment_type"),
        "status":       "received",
    }

    append_row("Ledger", payment)

    return {
        "event":   "payment_recorded",
        "payment": payment,
    }