"""
services/google_sheets_service.py
---------------------------------
Google Sheets ledger integration for Notiflow.

Appends a row to the configured Google Sheet every time a notification
is processed.  Uses a service-account JSON file for authentication.

Environment variables (loaded via python-dotenv):
    GOOGLE_SHEETS_CREDENTIALS  — path to the service-account JSON file
    GOOGLE_SHEET_ID            — the Sheet key (from the URL)

Row structure:
    [intent, item, quantity, customer, amount, source, timestamp]

If the Sheets API is unreachable or misconfigured, the service logs
the error and returns False — it NEVER crashes the pipeline.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-loaded module-level client
# ---------------------------------------------------------------------------

_sheet = None          # gspread.Worksheet (first sheet)
_initialised = False   # True after first attempt


def _get_sheet():
    """
    Lazy-initialise the gspread worksheet.

    Returns the worksheet on success, or None if credentials / sheet ID
    are missing or invalid.
    """
    global _sheet, _initialised

    if _initialised:
        return _sheet

    _initialised = True

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as exc:
        logger.warning("Google Sheets libraries not installed (%s). "
                       "Install gspread and google-auth.", exc)
        return None

    creds_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "credentials/sheets.json")
    sheet_id   = os.getenv("GOOGLE_SHEET_ID", "")

    if not sheet_id:
        logger.warning("GOOGLE_SHEET_ID not set — Sheets sync disabled.")
        return None

    # Resolve relative path from project root
    creds_file = Path(creds_path)
    if not creds_file.is_absolute():
        creds_file = Path(__file__).parent.parent / creds_file

    if not creds_file.exists():
        logger.warning("Google credentials file not found at %s", creds_file)
        return None

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_file(
            str(creds_file), scopes=scopes,
        )
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(sheet_id)
        _sheet = spreadsheet.sheet1          # first worksheet
        logger.info("Google Sheets connected: %s", spreadsheet.title)
        return _sheet
    except Exception as exc:
        logger.error("Failed to connect to Google Sheets: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def append_transaction(
    intent: str,
    data: dict[str, Any],
    source: str = "system",
) -> bool:
    """
    Append a ledger row to the configured Google Sheet.

    Args:
        intent:  Detected intent (e.g. "order", "payment").
        data:    Validated entity dict from the extraction agent.
        source:  Notification source (e.g. "whatsapp", "gpay").

    Returns:
        True if the row was written successfully, False otherwise.
    """
    ws = _get_sheet()
    if ws is None:
        logger.warning("Google Sheets update skipped — not connected.")
        return False

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    row = [
        intent,
        str(data.get("item", "")),
        str(data.get("quantity", "")),
        str(data.get("customer", "")),
        str(data.get("amount", "")),
        source,
        timestamp,
    ]

    # Defensive padding — always exactly 7 columns to prevent column drift
    row = (row + [""] * 7)[:7]

    try:
        ws.append_row(row, value_input_option="USER_ENTERED", table_range="A1")
        logger.info("Google Sheets ledger updated successfully")
        return True
    except Exception as exc:
        logger.error("Google Sheets update failed: %s", exc)
        return False
