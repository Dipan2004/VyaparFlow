"""
app/agents/extraction_agent.py
------------------------------
ExtractionAgent - Stage 2 of the NotiFlow pipeline.

Phase 5: Multi-intent support.
    - Reads context["intents"] (list); falls back to context["intent"]
    - Single LLM call extracts data for ALL intents at once
    - Writes context["multi_data"]  = {intent: {fields}}  (all intents)
    - Writes context["data"]        = multi_data[primary]  (backward compat)

Single-intent path is identical to Phase 1-4 behaviour, with deterministic
numeric fallbacks for order-like and payment-like phrases when the model
misses large numbers or leaves quantity empty.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.core.base_agent import BaseAgent
from app.core.context import update_context
from app.core.llm_service import get_llm

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "extraction_prompt.txt"

INTENT_SCHEMA: dict[str, list[str]] = {
    "order": ["customer", "item", "quantity"],
    "payment": ["customer", "amount", "payment_type"],
    "credit": ["customer", "item", "quantity", "amount"],
    "return": ["customer", "item", "reason"],
    "preparation": ["item", "quantity"],
    "other": ["note"],
}
VALID_INTENTS = set(INTENT_SCHEMA.keys())

_ITEM_ALIASES: dict[str, str] = {
    "kurta": "kurta",
    "kurti": "kurti",
    "kurti": "kurti",
    "chini": "chini",
    "sugar": "chini",
    "atta": "atta",
    "rice": "rice",
    "chawal": "rice",
}
_ITEM_PATTERN = r"|".join(sorted((re.escape(item) for item in _ITEM_ALIASES), key=len, reverse=True))
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")
_ORDER_QTY_PATTERNS = [
    re.compile(rf"\b(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilo|kilos|pcs|pieces?|piece|packet|packets|set|sets|nag|nos?)?\s*({_ITEM_PATTERN})\b", re.IGNORECASE),
    re.compile(rf"\b({_ITEM_PATTERN})\s*(?:x|qty)?\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE),
]
_PAYMENT_AMOUNT_PATTERNS = [
    re.compile(r"\b([A-Za-z][A-Za-z\s]{0,30}?)\s+ne\s+(\d+(?:\.\d+)?)\s+(?:bheja|bheje|bhej diya|diya|paid|pay(?:ed)?|transfer(?:red)?|clear(?:ed)?|jama)\b", re.IGNORECASE),
    re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:rs|rupaye|rupees)?\s*(?:bheja|bheje|bhej diya|diya|paid|pay(?:ed)?|transfer(?:red)?|clear(?:ed)?|jama)\b", re.IGNORECASE),
]


class ExtractionAgent(BaseAgent):
    """Extract structured business fields for all detected intents."""

    name = "ExtractionAgent"
    input_keys = ["message", "intent", "intents"]
    output_keys = ["data", "multi_data", "state"]
    action = "Extract structured entities for all detected intents"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        message = context.get("message", "").strip()

        intents = context.get("intents") or []
        if not intents:
            primary = (context.get("intent") or "other").lower().strip()
            intents = [primary]

        intents = [intent if intent in VALID_INTENTS else "other" for intent in intents]
        primary = intents[0]

        if not message:
            multi_data = {
                intent: self._extract_single({}, intent, "")
                for intent in intents
            }
            update_context(
                context,
                data=multi_data[primary],
                multi_data=multi_data,
                state="extracted",
            )
            return context

        prompt = self._load_prompt(message, intents)
        try:
            raw = get_llm().generate(
                prompt,
                max_tokens=400,
                agent_name=self.name,
                task_type="extraction",
                context=context,
            )
        except Exception as exc:
            logger.error("[ExtractionAgent] all LLM backends failed - using heuristic extraction: %s", exc)
            # Heuristic extraction: extract data from message keywords
            multi_data = ExtractionAgent._heuristic_extract(intents, message)
            update_context(
                context,
                data=multi_data[intents[0]] if intents else {},
                multi_data=multi_data,
                state="extracted",
            )
            logger.info("[ExtractionAgent] heuristic intents=%s extracted=%s", intents, multi_data)
            return context

        multi_data = self._parse(raw, intents, message)

        update_context(
            context,
            data=multi_data[primary],
            multi_data=multi_data,
            state="extracted",
        )
        logger.info("[ExtractionAgent] intents=%s extracted=%s", intents, multi_data)
        return context

    @staticmethod
    def _load_prompt(message: str, intents: list[str]) -> str:
        template = _PROMPT_PATH.read_text(encoding="utf-8")
        intents_str = ", ".join(intents)
        prompt = template.replace("{message}", message.strip())
        prompt = prompt.replace("{intents}", intents_str)
        prompt = prompt.replace("{intent}", intents_str)
        return prompt

    @staticmethod
    def _parse(raw: str, intents: list[str], message: str) -> dict[str, dict]:
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
        parsed: dict[str, Any] = {}
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    logger.warning("[ExtractionAgent] could not parse JSON; falling back to heuristics")

        multi_data: dict[str, dict] = {}

        if len(intents) == 1:
            intent = intents[0]
            multi_data[intent] = ExtractionAgent._extract_single(parsed, intent, message)
        else:
            for intent in intents:
                if intent in parsed and isinstance(parsed[intent], dict):
                    source = parsed[intent]
                elif not multi_data and intent == intents[0]:
                    source = parsed
                else:
                    source = {}
                multi_data[intent] = ExtractionAgent._extract_single(source, intent, message)

        for intent in intents:
            if intent not in multi_data:
                multi_data[intent] = ExtractionAgent._extract_single({}, intent, message)

        shared_customers = {
            str(data.get("customer")).strip().title()
            for data in multi_data.values()
            if isinstance(data.get("customer"), str) and str(data.get("customer")).strip()
        }
        if len(shared_customers) == 1:
            shared_customer = next(iter(shared_customers))
            for data in multi_data.values():
                if "customer" in data and not data.get("customer"):
                    data["customer"] = shared_customer

        return multi_data

    @staticmethod
    def _heuristic_extract(intents: list[str], message: str) -> dict[str, dict]:
        """
        Heuristic extraction: extract data from message keywords when LLM fails.
        """
        msg = message.lower()
        multi_data: dict[str, dict] = {}

        for intent in intents:
            data: dict[str, Any] = {}

            # Extract quantity FIRST (before amount) - look for item-specific patterns
            # e.g., "3 kurti", "2 shirt", "4 pant"
            qty_match = re.search(r'(\d+)\s+(?:kurti|shirt|pant|piece|pc|items?|quantity)', msg)
            if not qty_match:
                # Try general quantity at start
                qty_match = re.search(r'^(\d+)\s+(?:\w+\s+){0,2}(?:kurti|shirt|pant)', msg)
            if qty_match:
                try:
                    data['quantity'] = int(qty_match.group(1))
                except ValueError:
                    pass

            # Extract amount - look for amounts with rupees/rs/₹ or standalone large numbers
            # Only if quantity wasn't found or for payment intents
            if intent == 'payment' or 'quantity' not in data:
                amount_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:rs\.?|rupees?|₹)?', msg)
                if amount_match:
                    try:
                        data['amount'] = float(amount_match.group(1))
                    except ValueError:
                        pass

            # Extract customer name (word before "ne" or "said")
            customer_match = re.search(r'(\w+)\s+ne\s+', msg)
            if customer_match:
                data['customer'] = customer_match.group(1).title()
            else:
                # Try to find name at start
                customer_match = re.search(r'^(\w+)\s+', msg)
                if customer_match:
                    data['customer'] = customer_match.group(1).title()

            # Extract item
            if any(kw in msg for kw in ['kurti', 'shirt', 'pant', 'dress', 'suit']):
                data['item'] = 'clothing'
            elif any(kw in msg for kw in ['shoe', 'shoes', 'sandel']):
                data['item'] = 'footwear'
            else:
                data['item'] = 'goods'

            # Set payment type
            if intent == 'payment':
                data['payment_type'] = 'upi'

            multi_data[intent] = data

        return multi_data

    @staticmethod
    def _extract_single(src: dict[str, Any], intent: str, message: str) -> dict[str, Any]:
        schema = INTENT_SCHEMA.get(intent, INTENT_SCHEMA["other"])
        result = {field: src.get(field) for field in schema}
        lowered_message = message.lower()

        if "customer" in result and isinstance(result["customer"], str):
            result["customer"] = result["customer"].strip().title()
            if result["customer"].lower() in {"null", "none", ""}:
                result["customer"] = None

        if "item" in result:
            normalized_item = ExtractionAgent._normalize_item(result.get("item"))
            result["item"] = normalized_item or ExtractionAgent._detect_item(lowered_message)

        for numeric_field in ("amount", "quantity"):
            if numeric_field in result and result[numeric_field] is not None:
                result[numeric_field] = ExtractionAgent._to_number(result[numeric_field])

        if intent in {"order", "credit", "preparation"}:
            result["quantity"] = ExtractionAgent._infer_quantity(
                lowered_message,
                result.get("item"),
                result.get("quantity"),
            )

        if intent == "payment":
            inferred_amount, inferred_customer = ExtractionAgent._infer_payment_amount_and_customer(lowered_message)
            if result.get("amount") is None:
                result["amount"] = inferred_amount
            if result.get("customer") is None and inferred_customer:
                result["customer"] = inferred_customer

        if intent == "credit" and result.get("amount") is None:
            inferred_amount, inferred_customer = ExtractionAgent._infer_payment_amount_and_customer(lowered_message)
            if ExtractionAgent._contains_payment_cue(lowered_message):
                result["amount"] = inferred_amount
            if result.get("customer") is None and inferred_customer:
                result["customer"] = inferred_customer

        return result

    @staticmethod
    def _contains_payment_cue(message: str) -> bool:
        return any(
            cue in message
            for cue in ("bheja", "bheje", "paid", "diya", "transfer", "clear", "jama")
        )

    @staticmethod
    def _normalize_item(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip().lower()
        if not text or text in {"null", "none"}:
            return None
        return _ITEM_ALIASES.get(text, text)

    @staticmethod
    def _detect_item(message: str) -> str | None:
        for alias, normalized in _ITEM_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", message, re.IGNORECASE):
                return normalized
        return None

    @staticmethod
    def _to_number(value: Any) -> int | float | None:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            match = _NUMBER_PATTERN.search(str(value).replace(",", ""))
            if not match:
                return None
            numeric = float(match.group(0))
        return int(numeric) if numeric.is_integer() else numeric

    @staticmethod
    def _infer_quantity(message: str, item: Any, current_quantity: Any) -> int | float | None:
        normalized_quantity = ExtractionAgent._to_number(current_quantity)
        normalized_item = ExtractionAgent._normalize_item(item)

        if normalized_quantity is not None:
            return normalized_quantity

        if normalized_item:
            item_terms = [term for term, mapped in _ITEM_ALIASES.items() if mapped == normalized_item]
            item_pattern = r"|".join(sorted((re.escape(term) for term in item_terms), key=len, reverse=True))
            for pattern in (
                re.compile(rf"\b(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilo|kilos|pcs|pieces?|piece|packet|packets|set|sets|nag|nos?)?\s*({item_pattern})\b", re.IGNORECASE),
                re.compile(rf"\b({item_pattern})\s*(?:x|qty)?\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE),
            ):
                match = pattern.search(message)
                if match:
                    value = match.group(1) if ExtractionAgent._to_number(match.group(1)) is not None else match.group(2)
                    quantity = ExtractionAgent._to_number(value)
                    if quantity is not None:
                        return quantity
            return 1

        return normalized_quantity

    @staticmethod
    def _infer_payment_amount_and_customer(message: str) -> tuple[int | float | None, str | None]:
        for pattern in _PAYMENT_AMOUNT_PATTERNS:
            match = pattern.search(message)
            if not match:
                continue
            if len(match.groups()) == 2 and ExtractionAgent._to_number(match.group(2)) is not None:
                return ExtractionAgent._to_number(match.group(2)), match.group(1).strip().title()
            if len(match.groups()) >= 1:
                return ExtractionAgent._to_number(match.group(1)), None

        return None, None
