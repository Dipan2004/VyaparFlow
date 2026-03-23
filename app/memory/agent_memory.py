"""
agent_memory.py
---------------
Agent memory layer for Notiflow.

Stores recent business context so skills and future agents can reference
what was last discussed (customer names, items, etc.).

Storage: JSON file at the path defined in app/config.py (MEMORY_FILE).
Structure:
    {
        "recent_customers": ["Rahul", "Priya"],   # newest last
        "recent_items":     ["kurti", "aata"]
    }

Public API
----------
load_memory()  -> dict
update_memory(customer=None, item=None) -> None

Design notes:
  - Maximum 10 entries per list (oldest pruned automatically).
  - Read-modify-write is done in one function call to minimise race window.
  - None values are silently ignored (no-op).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from app.config import MEMORY_FILE

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 10

_EMPTY_MEMORY: dict = {
    "recent_customers": [],
    "recent_items":     [],
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_file() -> dict:
    """Read memory from disk; return empty structure if file missing/corrupt."""
    path = Path(MEMORY_FILE)
    if not path.exists():
        return {k: list(v) for k, v in _EMPTY_MEMORY.items()}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure both keys are present even if file is partial
        data.setdefault("recent_customers", [])
        data.setdefault("recent_items", [])
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read memory file (%s) — using empty memory.", exc)
        return {k: list(v) for k, v in _EMPTY_MEMORY.items()}


def _write_file(memory: dict) -> None:
    """Write memory dict to disk atomically (write to temp then rename)."""
    path    = Path(MEMORY_FILE)
    tmp     = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
        tmp.replace(path)
    except OSError as exc:
        logger.error("Could not write memory file: %s", exc)
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _append_unique(lst: list, value: str, max_size: int = _MAX_ENTRIES) -> list:
    """
    Append value to list, deduplicate, and keep only the most recent entries.
    Most recent item is always at the end.
    """
    if value in lst:
        lst.remove(value)          # remove old occurrence so it moves to end
    lst.append(value)
    return lst[-max_size:]         # keep newest max_size entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_memory() -> dict:
    """
    Load the current agent memory from disk.

    Returns:
        {
            "recent_customers": [str, ...],
            "recent_items":     [str, ...]
        }
    """
    memory = _read_file()
    logger.debug("Memory loaded: %s", memory)
    return memory


def update_memory(
    customer: Optional[str] = None,
    item:     Optional[str] = None,
) -> None:
    """
    Update agent memory with a new customer name and/or item.

    None values are silently ignored.
    Duplicates are deduplicated and moved to the end (most recent position).

    Args:
        customer: Customer name to remember (e.g. "Rahul").
        item:     Item name to remember (e.g. "kurti").

    Example:
        >>> update_memory(customer="Rahul", item="kurti")
    """
    if customer is None and item is None:
        return

    memory = _read_file()

    if customer:
        memory["recent_customers"] = _append_unique(
            memory["recent_customers"], str(customer).strip()
        )

    if item:
        memory["recent_items"] = _append_unique(
            memory["recent_items"], str(item).strip()
        )

    _write_file(memory)
    logger.info("Memory updated: customer=%s item=%s", customer, item)