"""
preparation_skill.py
--------------------
Business Skill: Preparation / Inventory Pack  (Stage 6 — with persistence)

Handles the "preparation" intent.
Appends a preparation task to the Inventory sheet as a "reserved" movement.

This records that stock is being set aside / packed, without fully
deducting it (deduction happens when the linked order ships).
If no linked order exists (standalone prep task), the record still logs
the intention for the shop owner's reference.

Expected input fields:
    item      (str | None)  — item to prepare or pack
    quantity  (int | None)  — number of units to prepare
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


def _generate_prep_id() -> str:
    """Generate a sequential preparation ID: PREP-YYYYMMDD-XXXX."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    # Count existing preparation entries in Inventory to sequence the ID
    df  = read_sheet("Inventory")
    prep_rows = df[df["direction"] == "reserved"] if not df.empty and "direction" in df.columns else df
    seq = len(prep_rows) + 1
    return f"PREP-{today}-{seq:04d}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_preparation(data: dict) -> dict:
    """
    Process a preparation / packing task and log it to the Inventory sheet.

    The movement is logged with direction="reserved" so it is visible in
    the inventory log but does not reduce the available stock count until
    the items actually ship.

    Args:
        data: Extracted fields dict from the Extraction Agent.
              Expected keys: item, quantity

    Returns:
        {
            "event":       "preparation_queued",
            "preparation": {
                "prep_id":   str,
                "timestamp": ISO-8601 str,
                "item":      str | None,
                "quantity":  int | None,
                "status":    "queued"
            }
        }

    Example:
        >>> process_preparation({"item": "kurti", "quantity": 3})
        {
            "event": "preparation_queued",
            "preparation": {
                "prep_id": "PREP-20240115-0001",
                "timestamp": "...",
                "item": "kurti",
                "quantity": 3,
                "status": "queued"
            }
        }
    """
    logger.info("PreparationSkill processing: %s", data)

    item     = data.get("item")
    quantity = data.get("quantity")
    prep_id  = _generate_prep_id()

    # Log to Inventory sheet as a "reserved" movement
    if item:
        inventory_record = {
            "timestamp":    _now_iso(),
            "item":         item,
            "change":       quantity or 0,
            "direction":    "reserved",
            "reference_id": prep_id,
            "note":         "preparation task queued",
        }
        append_row("Inventory", inventory_record)

    prep = {
        "prep_id":   prep_id,
        "timestamp": _now_iso(),
        "item":      item,
        "quantity":  quantity,
        "status":    "queued",
    }

    logger.info("Preparation task logged: %s", prep_id)

    return {
        "event":       "preparation_queued",
        "preparation": prep,
    }