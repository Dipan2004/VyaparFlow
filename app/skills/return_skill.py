"""
return_skill.py
---------------
Business Skill: Return / Exchange  (Stage 6 — with persistence)

Handles the "return" intent.
Appends a return record to the Returns sheet in notiflow_data.xlsx.

Inventory is NOT updated here. Stock is only added back once the return
status changes to "approved" — to be handled in a future stage via a
status-update workflow.

Expected input fields:
    customer  (str | None)  — customer making the return
    item      (str | None)  — item being returned or exchanged
    reason    (str | None)  — reason for return (e.g. "size issue", "damaged")
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


def _generate_return_id() -> str:
    """Generate a sequential return ID: RET-YYYYMMDD-XXXX."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    df    = read_sheet("Returns")
    seq   = len(df) + 1
    return f"RET-{today}-{seq:04d}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_return(data: dict) -> dict:
    """
    Process a return / exchange event and persist it to the Returns sheet.

    Inventory is NOT updated here — stock is only restored after approval.

    Args:
        data: Extracted fields dict from the Extraction Agent.
              Expected keys: customer, item, reason

    Returns:
        {
            "event":  "return_requested",
            "return": {
                "return_id": str,
                "timestamp": ISO-8601 str,
                "customer":  str | None,
                "item":      str | None,
                "reason":    str | None,
                "status":    "pending_review"
            }
        }

    Example:
        >>> process_return({"customer": None, "item": None, "reason": "size issue"})
        {
            "event": "return_requested",
            "return": {
                "return_id": "RET-20240115-0001",
                "timestamp": "...",
                "customer": None,
                "item": None,
                "reason": "size issue",
                "status": "pending_review"
            }
        }
    """
    logger.info("ReturnSkill processing: %s", data)

    return_id = _generate_return_id()

    return_entry = {
        "return_id": return_id,
        "timestamp": _now_iso(),
        "customer":  data.get("customer"),
        "item":      data.get("item"),
        "reason":    data.get("reason"),
        "status":    "pending_review",
    }

    append_row("Returns", return_entry)
    logger.info("Return logged: %s", return_id)

    return {
        "event":  "return_requested",
        "return": return_entry,
    }