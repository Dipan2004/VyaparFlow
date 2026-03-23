"""
data_validator.py
-----------------
Validation and normalization utilities for extracted business data.

Used in the orchestrator pipeline between extraction and skill routing:

    extract_fields() → validate_data() → route_to_skill()

The validator normalises:
  - text fields (customer, item, reason)  → stripped, lowercased or title-cased
  - payment_type aliases (gpay → upi, paytm → upi, etc.)
  - numeric fields (amount, quantity)     → int or float, never negative
"""

from __future__ import annotations

import re
from typing import Any


_NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


class DataValidator:
    """Validate and normalize extraction-agent output."""

    def validate(self, intent: str, data: dict[str, Any]) -> dict[str, Any]:
        """Return a cleaned copy of extracted data for the given intent."""
        cleaned = dict(data or {})

        if "customer" in cleaned:
            cleaned["customer"] = self._clean_text(cleaned.get("customer"), title=True)
        if "item" in cleaned:
            cleaned["item"] = self._clean_text(cleaned.get("item"))
        if "reason" in cleaned:
            cleaned["reason"] = self._clean_text(cleaned.get("reason"))
        if "payment_type" in cleaned:
            cleaned["payment_type"] = self._normalize_payment_type(cleaned.get("payment_type"))
        if "amount" in cleaned:
            cleaned["amount"] = self._to_number(cleaned.get("amount"), as_int_if_possible=True)
        if "quantity" in cleaned:
            cleaned["quantity"] = self._to_number(cleaned.get("quantity"), as_int_if_possible=True)

        # Business rules: amounts and quantities must be positive
        if intent == "payment" and cleaned.get("amount") is not None and cleaned["amount"] < 0:
            cleaned["amount"] = abs(cleaned["amount"])
        if (
            intent in {"order", "credit", "preparation"}
            and cleaned.get("quantity") is not None
            and cleaned["quantity"] < 0
        ):
            cleaned["quantity"] = abs(cleaned["quantity"])

        return cleaned

    @staticmethod
    def _clean_text(value: Any, *, title: bool = False) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        text = re.sub(r"\s+", " ", text)
        return text.title() if title else text.lower()

    @staticmethod
    def _normalize_payment_type(value: Any) -> str | None:
        text = DataValidator._clean_text(value)
        if text is None:
            return None

        aliases = {
            "gpay":          "upi",
            "google pay":    "upi",
            "phonepe":       "upi",
            "phone pe":      "upi",
            "paytm":         "upi",
            "upi":           "upi",
            "cash":          "cash",
            "online":        "online",
            "bank transfer": "online",
            "neft":          "online",
            "imps":          "online",
            "rtgs":          "online",
            "cheque":        "cheque",
            "check":         "cheque",
        }
        return aliases.get(text, text)

    @staticmethod
    def _to_number(value: Any, *, as_int_if_possible: bool = False) -> int | float | None:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number = float(value)
        else:
            text  = str(value).replace(",", "").lower()
            match = _NUMBER_PATTERN.search(text)
            if not match:
                return None
            number = float(match.group(0))
        if as_int_if_possible and number.is_integer():
            return int(number)
        return number


# ---------------------------------------------------------------------------
# Convenience wrapper — used by the orchestrator
# ---------------------------------------------------------------------------

def validate_data(intent: str, data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalise and validate extracted data for the given intent.

    This is the function the orchestrator imports:

        # (this is the canonical location — no re-import needed)
        cleaned = validate_data(intent, raw_data)

    Args:
        intent: Detected intent string (e.g. "payment", "order").
        data:   Raw extraction dict from the Extraction Agent.

    Returns:
        Cleaned, normalised copy of the data dict.
    """
    return DataValidator().validate(intent, data)