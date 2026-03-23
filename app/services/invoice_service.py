"""
invoice_service.py
------------------
Invoice generation service for Notiflow.

Responsibility: generate a structured invoice object only.
Excel persistence is handled separately by the skill layer.

Invoice ID format: INV-YYYYMMDD-XXXX
    - YYYYMMDD  today's UTC date
    - XXXX      4-character alphanumeric suffix (uppercase)

Public API
----------
generate_invoice(customer, item, quantity, unit_price=0.0) -> dict
"""

from __future__ import annotations

import random
import string
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_invoice_id() -> str:
    """
    Format: INV-YYYYMMDD-XXXX
    XXXX = random 4-char uppercase alphanumeric suffix.
    No file read needed — random suffix avoids collisions for demo scale.
    """
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix    = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"INV-{date_part}-{suffix}"


def generate_invoice(
    customer:   Optional[str],
    item:       Optional[str],
    quantity:   Optional[int | float],
    unit_price: float = 0.0,
    order_id:   Optional[str] = None,
) -> dict:
    """
    Generate a structured invoice object.

    Does NOT write to Excel — the calling skill persists the result.

    Args:
        customer:   Customer name (may be None).
        item:       Item name (may be None).
        quantity:   Quantity ordered (may be None).
        unit_price: Price per unit. Defaults to 0.0.
        order_id:   Optional linked order ID.

    Returns:
        {
            "invoice_id":   "INV-20260315-AB12",
            "timestamp":    ISO-8601 str,
            "order_id":     str | None,
            "customer":     str | None,
            "item":         str | None,
            "quantity":     int | float | None,
            "unit_price":   float,
            "total_amount": float,
            "status":       "pending"
        }
    """
    invoice_id   = _make_invoice_id()
    qty          = quantity or 0
    total_amount = round(float(qty) * unit_price, 2)

    invoice = {
        "invoice_id":   invoice_id,
        "timestamp":    _now_iso(),
        "order_id":     order_id,
        "customer":     customer,
        "item":         item,
        "quantity":     quantity,
        "unit_price":   unit_price,
        "total_amount": total_amount,
        "status":       "pending",
    }

    logger.info(
        "Invoice generated: %s | customer=%s item=%s qty=%s total=%.2f",
        invoice_id, customer, item, quantity, total_amount,
    )
    return invoice