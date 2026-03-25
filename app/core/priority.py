"""
app/core/priority.py
---------------------
Shared priority scoring utilities for NotiFlow Autonomous.

Replaces the single-agent string assignment pattern with an
additive scoring model.  Any agent can contribute points.
UrgencyAgent is the sole agent that derives the final label.

Score scale: 0 – 100 (int, clamped)
    > 70  → "high"
    > 40  → "medium"
    ≤ 40  → "low"

Public API
----------
contribute_priority_score(ctx, points, reason) -> None
    Add points to context["priority_score"] and log the reason.

derive_priority_label(ctx) -> str
    Read context["priority_score"] and return the label string.
    Also writes context["priority"] = label and returns it.

reset_priority_score(ctx) -> None
    Zero the score (used at replan boundaries).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_SCORE_KEY   = "priority_score"
_REASONS_KEY = "priority_score_reasons"

# Thresholds
_HIGH_THRESHOLD   = 70
_MEDIUM_THRESHOLD = 40


def contribute_priority_score(
    ctx:    dict[str, Any],
    points: int,
    reason: str,
) -> None:
    """
    Add points (0–100 scale) to the running priority score.

    Points are clamped so the total never exceeds 100.
    The reason is appended to context["priority_score_reasons"] for audit.

    Args:
        ctx:    The live request context dict.
        points: Integer contribution (positive only).
        reason: Human-readable explanation of why this score was added.
    """
    if points <= 0:
        return
    current = ctx.get(_SCORE_KEY, 0)
    new_val  = min(100, current + points)
    ctx[_SCORE_KEY] = new_val
    ctx.setdefault(_REASONS_KEY, []).append(
        {"points": points, "reason": reason, "total_after": new_val}
    )
    logger.debug(
        "[Priority] +%d (%s) → total=%d", points, reason, new_val
    )


def derive_priority_label(ctx: dict[str, Any]) -> str:
    """
    Derive the final priority label from the accumulated score.

    Writes context["priority"] = label and returns the label.

    Args:
        ctx: The live request context dict.

    Returns:
        "high" | "medium" | "low"
    """
    score = ctx.get(_SCORE_KEY, 0)
    if score > _HIGH_THRESHOLD:
        label = "high"
    elif score > _MEDIUM_THRESHOLD:
        label = "medium"
    else:
        label = "low"
    ctx["priority"] = label
    logger.info(
        "[Priority] score=%d → label=%s", score, label
    )
    return label


def reset_priority_score(ctx: dict[str, Any]) -> None:
    """
    Reset the priority score to 0 (used at replan boundaries).

    Args:
        ctx: The live request context dict.
    """
    ctx[_SCORE_KEY]   = 0
    ctx[_REASONS_KEY] = []