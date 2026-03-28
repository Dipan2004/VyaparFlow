from __future__ import annotations

import logging
from typing import Any

from app.core.base_agent import BaseAgent
from app.core.context import update_context
from app.core.event_bus import emit_event, push_live_log, store_invoice
from app.services.invoice_service import InvoiceBuilder

logger = logging.getLogger(__name__)

PRICE_MAP = {
    "kurti": 50.0,
    "sugar": 50.0,
    "atta": 40.0,
}


class InvoiceAgent(BaseAgent):
    """Generate a business invoice from validated order data."""

    name = "InvoiceAgent"
    input_keys = ["intent", "data", "source"]
    output_keys = ["invoice", "event", "state"]
    action = "Generate invoice from validated business data"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        intent = (context.get("intent") or "other").lower()
        data = context.get("data", {}) or {}

        if intent != "order":
            update_context(
                context,
                event={"event": f"{intent}_received", "data": data},
                state="invoice_skipped",
            )
            return context

        builder = InvoiceBuilder(catalog_prices=PRICE_MAP)
        invoice = builder.build(
            customer=data.get("customer") or "Walk-in customer",
            item=data.get("item"),
            quantity=data.get("quantity"),
            order_id=context.get("event", {}).get("order_id"),
        )
        invoice = store_invoice(invoice)

        update_context(
            context,
            invoice=invoice,
            event={"event": "invoice_generated", "invoice": invoice},
            state="invoice_generated",
        )

        invoice_log = push_live_log(
            context,
            {
                "agent": self.name,
                "status": "success",
                "action": f"Invoice generated: {invoice['invoice_id']}",
                "detail": f"[{self.name}] Invoice generated: {invoice['invoice_id']}",
            },
        )
        emit_event(
            context,
            "invoice_generated",
            invoice,
            agent=self.name,
            step="invoice",
            message=f"Invoice generated: {invoice['invoice_id']}",
            log_entry=invoice_log,
        )
        logger.info("[InvoiceAgent] invoice=%s", invoice["invoice_id"])
        return context
