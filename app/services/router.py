"""
router.py
---------
Stage 5: Skill Router for Notiflow

The Skill Router is the decision layer between the Extraction Agent
and the Business Skills. It receives a structured event (intent + data)
and dispatches to the correct skill.

Routing table:

    intent          → skill function
    ─────────────────────────────────
    order           → process_order()
    payment         → process_payment()
    credit          → process_credit()
    return          → process_return()
    preparation     → process_preparation()
    other           → (no skill; passthrough)

If an intent has no registered skill the router returns a lightweight
passthrough event so the pipeline never raises on unknown intents.
"""

import logging
from typing import Any

from app.skills.order_skill       import process_order
from app.skills.payment_skill     import process_payment
from app.skills.credit_skill      import process_credit
from app.skills.return_skill      import process_return
from app.skills.preparation_skill import process_preparation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Routing table  (intent → skill callable)
# ---------------------------------------------------------------------------

_SKILL_MAP: dict[str, Any] = {
    "order":       process_order,
    "payment":     process_payment,
    "credit":      process_credit,
    "return":      process_return,
    "preparation": process_preparation,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def route_to_skill(intent: str, data: dict) -> dict:
    """
    Route a structured business event to the appropriate skill.

    Args:
        intent: The detected intent string (e.g. "payment", "order").
        data:   The extracted field dict returned by the Extraction Agent
                (without the "intent" key — that lives at the top level).

    Returns:
        A skill event dict.  Structure varies per skill but always contains
        at minimum an "event" key describing what happened.

        For unrecognised / "other" intents a passthrough dict is returned:
        {"event": "unhandled", "intent": intent, "data": data}

    Example:
        >>> route_to_skill("payment", {"customer": "Rahul", "amount": 15000})
        {
            "event": "payment_recorded",
            "payment": {"customer": "Rahul", "amount": 15000, "status": "received"}
        }
    """
    skill_fn = _SKILL_MAP.get(intent)

    if skill_fn is None:
        logger.info("No skill registered for intent '%s' — returning passthrough.", intent)
        return {"event": "unhandled", "intent": intent, "data": data}

    logger.info("Routing intent '%s' to skill: %s", intent, skill_fn.__name__)
    return skill_fn(data)