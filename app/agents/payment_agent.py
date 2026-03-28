from __future__ import annotations

import logging
from typing import Any

from app.core.base_agent import BaseAgent
from app.core.context import update_context
from app.core.event_bus import emit_event, push_live_log

logger = logging.getLogger(__name__)


class PaymentAgent(BaseAgent):
    """Prepare pending payment state for generated invoices."""

    name = "PaymentAgent"
    input_keys = ["intent", "invoice"]
    output_keys = ["payment", "state"]
    action = "Prepare payment request from invoice state"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        intent = (context.get("intent") or "other").lower()
        invoice = context.get("invoice")

        if intent != "order" or not invoice:
            update_context(context, state="payment_skipped")
            return context

        payment = {
            "invoice_id": invoice.get("invoice_id"),
            "amount": invoice.get("total") or invoice.get("total_amount") or 0,
            "status": "pending",
        }
        update_context(context, payment=payment, state="payment_requested")

        payment_log = push_live_log(
            context,
            {
                "agent": self.name,
                "status": "success",
                "action": f"Payment requested for {invoice['invoice_id']}",
                "detail": f"[{self.name}] Payment requested: {invoice['invoice_id']}",
            },
        )
        emit_event(
            context,
            "payment_requested",
            {
                **invoice,
                "payment": payment,
            },
            agent=self.name,
            step="payment",
            message=f"Payment requested for {invoice['invoice_id']}",
            log_entry=payment_log,
        )
        logger.info("[PaymentAgent] payment requested for %s", invoice["invoice_id"])
        return context
