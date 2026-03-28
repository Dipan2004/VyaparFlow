"""
app/agents/ledger_agent.py
--------------------------
LedgerAgent — Stage 5 of the NotiFlow pipeline.

Wraps services/google_sheets_service.py into the BaseAgent interface.
Appends the processed transaction to the live Google Sheets ledger.

Non-fatal: if Sheets is unavailable the pipeline continues normally and
context["metadata"]["sheet_updated"] is set to False.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.base_agent import BaseAgent
from app.core.context import add_error

logger = logging.getLogger(__name__)


class LedgerAgent(BaseAgent):
    """Sync the processed transaction to the Google Sheets ledger."""

    name        = "LedgerAgent"
    input_keys  = ["intent", "data", "invoice", "payment", "metadata"]
    output_keys = ["metadata", "state"]
    action      = "Append transaction row to Google Sheets ledger"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Append a row to Google Sheets.

        Non-fatal design: ALL exceptions from the Sheets API are caught here
        inside execute() and recorded via add_error().  The method never
        raises, so BaseAgent.run() always logs a "success" history entry —
        reflecting that the agent completed its contract (best-effort sync),
        not that Sheets itself succeeded.

        Reads:  context["intent"], context["data"], context["metadata"]["source"]
        Writes: context["metadata"]["sheet_updated"]
        """
        intent = context.get("intent", "other")
        data   = context.get("data", {})
        invoice = context.get("invoice") or {}
        payment = context.get("payment") or {}
        source = context.get("metadata", {}).get("source", "system")

        ledger_data = {
            "customer": invoice.get("customer") or data.get("customer"),
            "item": invoice.get("item") or data.get("item"),
            "quantity": invoice.get("quantity") or data.get("quantity"),
            "amount": payment.get("amount") or invoice.get("total") or data.get("amount"),
            "invoice_id": invoice.get("invoice_id"),
            "status": payment.get("status") or invoice.get("status"),
        }

        sheet_updated = False
        try:
            from app.services.google_sheets_service import append_transaction
            sheet_updated = append_transaction(intent=intent, data=ledger_data, source=source)
        except Exception as exc:
            # Soft failure — record the error but do NOT raise.
            # This keeps LedgerAgent non-fatal without overriding run().
            logger.warning("[LedgerAgent] Sheets sync failed (%s) — continuing", exc)
            add_error(context, f"LedgerAgent: {exc}")

        context.setdefault("metadata", {})["sheet_updated"] = sheet_updated
        logger.info("[LedgerAgent] sheet_updated=%s", sheet_updated)
        return context
