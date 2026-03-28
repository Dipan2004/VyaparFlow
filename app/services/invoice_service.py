"""
invoice_service.py
------------------
Invoice generation service for Notiflow.

Responsibility: build a structured invoice object only.
Excel persistence is handled separately by the skill layer.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

PRICE_MAP: dict[str, float] = {
    "kurta": 50.0,
    "kurti": 80.0,
    "chini": 50.0,
    "atta": 40.0,
}

# Public catalog kept for backward compatibility with existing imports.
CATALOG_PRICES: dict[str, float] = {
    **PRICE_MAP,
    "sugar": 50.0,
    "rice": 60.0,
    "chawal": 60.0,
}
_CATALOG_PRICES = CATALOG_PRICES


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_invoice_id() -> str:
    return f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"


class InvoiceBuilder:
    """Create normalized invoice payloads from item, quantity, and optional price."""

    def __init__(self, catalog_prices: dict[str, float] | None = None):
        self.catalog_prices = catalog_prices or _CATALOG_PRICES

    def build(
        self,
        *,
        customer: Optional[str],
        item: Optional[str],
        quantity: Optional[int | float],
        price: Optional[float] = None,
        order_id: Optional[str] = None,
    ) -> dict:
        invoice_id = _make_invoice_id()
        normalized_item = (item or "").strip().lower() or None
        qty = 1 if quantity is None else float(quantity)
        if qty.is_integer():
            qty = int(qty)

        unit_price = self._resolve_price(normalized_item, price)
        total_amount = round(float(qty) * unit_price, 2)

        invoice = {
            "id": invoice_id,
            "invoice_id": invoice_id,
            "timestamp": _now_iso(),
            "order_id": order_id,
            "customer": customer,
            "items": [{"name": normalized_item, "qty": qty, "price": unit_price}],
            "item": normalized_item,
            "quantity": qty,
            "unit_price": unit_price,
            "total": total_amount,
            "total_amount": total_amount,
            "status": "pending",
        }

        logger.info(
            "Invoice generated: %s | customer=%s item=%s qty=%s total=%.2f",
            invoice_id, customer, normalized_item, qty, total_amount,
        )
        return invoice

    def _resolve_price(self, item: str | None, override_price: Optional[float]) -> float:
        if override_price is not None:
            return float(override_price)
        if not item:
            return float(PRICE_MAP["kurta"])
        return float(self.catalog_prices.get(item.lower(), PRICE_MAP.get(item.lower(), 50.0)))


def generate_invoice(
    customer: Optional[str],
    item: Optional[str],
    quantity: Optional[int | float],
    unit_price: float | None = None,
    order_id: Optional[str] = None,
) -> dict:
    builder = InvoiceBuilder()
    return builder.build(
        customer=customer,
        item=item,
        quantity=quantity,
        price=unit_price,
        order_id=order_id,
    )
