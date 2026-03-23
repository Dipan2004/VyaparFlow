"""
inventory_service.py
--------------------
Stage 6: Inventory Service for Notiflow

Tracks stock movements as a delta log in the Inventory Excel sheet.
Each event appends one row recording what changed, by how much,
and in which direction (in / out).

Design: delta-log (not current-stock snapshot)
    - Every inventory change is a new row
    - Current stock for an item = sum of all deltas for that item
    - This keeps the history intact and avoids row-update complexity

Directions:
    "out"  — stock leaves (order fulfilled)
    "in"   — stock arrives (return accepted, restock)
"""

import logging
from datetime import datetime, timezone

from app.utils.excel_writer import append_row, read_sheet

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def deduct_stock(item: str, quantity: int | float, reference_id: str, note: str = "") -> dict:
    """
    Record a stock deduction (items going out — e.g. an order is fulfilled).

    Args:
        item:         Name of the inventory item.
        quantity:     Number of units being deducted.
        reference_id: ID of the triggering record (e.g. order_id, invoice_id).
        note:         Optional human-readable note.

    Returns:
        The inventory movement record that was persisted.

    Example:
        >>> deduct_stock("kurti", 3, "ORD-20240115-0001", "order fulfilled")
        {
            "timestamp": "...",
            "item": "kurti",
            "change": 3,
            "direction": "out",
            "reference_id": "ORD-20240115-0001",
            "note": "order fulfilled"
        }
    """
    if quantity is None or quantity <= 0:
        logger.warning("deduct_stock called with invalid quantity: %s", quantity)
        return {}

    record = {
        "timestamp":    _now_iso(),
        "item":         item,
        "change":       quantity,
        "direction":    "out",
        "reference_id": reference_id,
        "note":         note or "stock deducted",
    }

    append_row("Inventory", record)
    logger.info("Stock deducted: %s × %s (ref: %s)", quantity, item, reference_id)
    return record


def add_stock(item: str, quantity: int | float, reference_id: str, note: str = "") -> dict:
    """
    Record a stock addition (items coming in — e.g. a return is accepted).

    Args:
        item:         Name of the inventory item.
        quantity:     Number of units being added.
        reference_id: ID of the triggering record (e.g. return_id).
        note:         Optional human-readable note.

    Returns:
        The inventory movement record that was persisted.
    """
    if quantity is None or quantity <= 0:
        logger.warning("add_stock called with invalid quantity: %s", quantity)
        return {}

    record = {
        "timestamp":    _now_iso(),
        "item":         item,
        "change":       quantity,
        "direction":    "in",
        "reference_id": reference_id,
        "note":         note or "stock added",
    }

    append_row("Inventory", record)
    logger.info("Stock added: %s × %s (ref: %s)", quantity, item, reference_id)
    return record


def get_stock_level(item: str) -> int | float:
    """
    Calculate the current stock level for an item by summing all deltas.

    Args:
        item: Name of the inventory item (case-insensitive match).

    Returns:
        Net stock level (int or float). Returns 0 if no records found.

    Example:
        >>> get_stock_level("kurti")
        47
    """
    df = read_sheet("Inventory")

    if df.empty or "item" not in df.columns:
        return 0

    item_rows = df[df["item"].str.lower() == item.lower()]

    if item_rows.empty:
        return 0

    total = 0
    for _, row in item_rows.iterrows():
        change    = row.get("change", 0) or 0
        direction = row.get("direction", "out")
        if direction == "in":
            total += change
        else:
            total -= change

    return max(total, 0)   # Stock can't go below 0 in the display