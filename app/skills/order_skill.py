"""
order_skill.py
--------------
Business Skill: Order  (Stage 6 + UPGRADE 1 — memory update)

On each order event this skill:
    1. Appends an order record to the Orders sheet
    2. Deducts stock from Inventory (delta log)
    3. Generates an invoice object and saves it to Invoices sheet
    4. Updates agent memory with customer + item        ← NEW (Upgrade 1)

Expected input fields (all may be None if not captured):
    customer  (str | None)
    item      (str | None)
    quantity  (int | None)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.event_bus             import emit_event, push_live_log, store_invoice
from app.utils.excel_writer         import append_row, read_sheet
from app.services.invoice_service   import generate_invoice
from app.services.inventory_service import deduct_stock
from app.memory.agent_memory        import update_memory

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_order_id() -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    df    = read_sheet("Orders")
    seq   = len(df) + 1
    return f"ORD-{today}-{seq:04d}"


def process_order(data: dict, context: dict | None = None) -> dict:
    """
    Process an order event: persist order, update inventory, generate invoice,
    and update agent memory.

    Args:
        data: Validated extraction dict. Keys: customer, item, quantity.

    Returns:
        {
            "event":   "order_received",
            "order":   { order record },
            "invoice": { invoice record }
        }
    """
    logger.info("OrderSkill ← %s", data)

    customer = data.get("customer")
    item     = data.get("item")
    quantity = data.get("quantity")
    order_id = _generate_order_id()

    # 1 ── Persist order ──────────────────────────────────────────────────────
    order = {
        "order_id":  order_id,
        "timestamp": _now_iso(),
        "customer":  customer,
        "item":      item,
        "quantity":  quantity,
        "status":    "pending",
    }
    append_row("Orders", order)

    # 2 ── Inventory deduction ────────────────────────────────────────────────
    if item and quantity:
        deduct_stock(item, quantity, reference_id=order_id, note="order fulfilled")

    # 3 ── Invoice generation ─────────────────────────────────────────────────
    invoice = generate_invoice(
        customer  = customer,
        item      = item,
        quantity  = quantity,
        order_id  = order_id,
    )
    invoice = store_invoice(invoice)
    append_row("Invoices", invoice)
    if context is not None:
        context["invoice"] = invoice
        invoice_log = push_live_log(context, {
            "agent": "ExecutionAgent",
            "status": "success",
            "action": f"Invoice created: {invoice['invoice_id']}",
            "detail": f"[ExecutionAgent] Invoice created: {invoice['invoice_id']}",
        })
        emit_event(
            context,
            "invoice_generated",
            invoice,
            agent="ExecutionAgent",
            step="execution",
            message=f"Invoice created: {invoice['invoice_id']}",
            log_entry=invoice_log,
        )
        payment_log = push_live_log(context, {
            "agent": "ExecutionAgent",
            "status": "success",
            "action": f"Payment requested for {invoice['invoice_id']}",
            "detail": f"[ExecutionAgent] Payment requested: {invoice['invoice_id']}",
        })
        emit_event(
            context,
            "payment_requested",
            invoice,
            agent="ExecutionAgent",
            step="payment",
            message=f"Payment requested for {invoice['invoice_id']}",
            log_entry=payment_log,
        )

    # 4 ── Memory update ──────────────────────────────────────────────────────
    update_memory(customer=customer, item=item)

    return {
        "event":   "order_received",
        "order":   order,
        "invoice": invoice,
    }
