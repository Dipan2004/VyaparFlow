"""
app/core/llm_router.py
-----------------------
LLM Router for NotiFlow Autonomous — Phase 4.

Maps (agent_name, task_type) → ordered list of models to try.
Pure data + logic, zero I/O.  LLMService consumes this.

Model entry shape:
    {
        "provider": "nim" | "openrouter",
        "model":    str,               # exact model ID
        "max_tokens": int | None,      # None = caller decides
    }

Routing strategy
----------------
                        primary                fallback-1              fallback-2
intent      →  deepseek-v3.2 (nim)   deepseek-v3.1 (nim)    openrouter-fallback
extraction  →  deepseek-v3.2 (nim)   deepseek-v3.1 (nim)    openrouter-fallback
planning    →  deepseek-v3.2 (nim)   openrouter-fallback     deepseek-v3.1 (nim)
reasoning   →  deepseek-v3.2 (nim)   openrouter-fallback     deepseek-v3.1 (nim)
default     →  deepseek-v3.2 (nim)   deepseek-v3.1 (nim)    openrouter-fallback

Extending
---------
Add / change routing by editing _ROUTES below.  No other file needs to change.

Public API
----------
route_llm(agent_name, task_type) -> dict
    Returns {"primary": ModelEntry, "fallbacks": [ModelEntry, ...]}

ModelEntry = {"provider": str, "model": str, "max_tokens": int | None}
"""

from __future__ import annotations

import os
from typing import TypedDict


class ModelEntry(TypedDict):
    provider:   str           # "nim" | "openrouter"
    model:      str           # model identifier
    max_tokens: int | None    # None = use caller default


# ---------------------------------------------------------------------------
# Model catalogue
# ---------------------------------------------------------------------------

_NIM_PRIMARY  : ModelEntry = {
    "provider":   "nim",
    "model":      os.getenv("NIM_PRIMARY_MODEL", "deepseek-ai/deepseek-v3"),
    "max_tokens": None,
}
_NIM_FALLBACK : ModelEntry = {
    "provider":   "nim",
    "model":      os.getenv("NIM_FALLBACK_MODEL", "deepseek-ai/deepseek-r1"),
    "max_tokens": None,
}
_OPENROUTER   : ModelEntry = {
    "provider":   "openrouter",
    "model":      os.getenv(
        "OPENROUTER_MODEL",
        "deepseek/deepseek-chat",   # sensible default
    ),
    "max_tokens": None,
}


# ---------------------------------------------------------------------------
# Routing table
# (agent_name, task_type) → [primary, fallback1, fallback2, ...]
# Keys are lowercased at lookup time.
# ---------------------------------------------------------------------------

_ROUTES: dict[tuple[str, str], list[ModelEntry]] = {

    # Fast classification — intent detection
    ("intentagent",      "classification"):  [_NIM_PRIMARY, _NIM_FALLBACK, _OPENROUTER],
    ("intentagent",      ""):                [_NIM_PRIMARY, _NIM_FALLBACK, _OPENROUTER],

    # Structured extraction — needs reliable JSON output
    ("extractionagent",  "extraction"):      [_NIM_PRIMARY, _NIM_FALLBACK, _OPENROUTER],
    ("extractionagent",  ""):                [_NIM_PRIMARY, _NIM_FALLBACK, _OPENROUTER],

    # Planning requires deeper reasoning
    ("planner",          "planning"):        [_NIM_PRIMARY, _OPENROUTER, _NIM_FALLBACK],
    ("planner",          ""):                [_NIM_PRIMARY, _OPENROUTER, _NIM_FALLBACK],

    # Reasoning-heavy agents — prediction, recovery
    ("predictionagent",  "reasoning"):       [_NIM_PRIMARY, _OPENROUTER, _NIM_FALLBACK],
    ("predictionagent",  ""):                [_NIM_PRIMARY, _OPENROUTER, _NIM_FALLBACK],
    ("recoveryagent",    "reasoning"):       [_NIM_PRIMARY, _OPENROUTER, _NIM_FALLBACK],
    ("recoveryagent",    ""):                [_NIM_PRIMARY, _OPENROUTER, _NIM_FALLBACK],
}

# Default route when no specific entry is found
_DEFAULT_ROUTE: list[ModelEntry] = [_NIM_PRIMARY, _NIM_FALLBACK, _OPENROUTER]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def route_llm(agent_name: str = "", task_type: str = "") -> dict:
    """
    Return the model routing plan for a given agent and task type.

    Args:
        agent_name: Class name of the calling agent (e.g. "IntentAgent").
                    Case-insensitive.
        task_type:  Nature of the task (e.g. "classification", "extraction",
                    "reasoning", "planning").  Case-insensitive.

    Returns:
        {
            "primary":   ModelEntry,
            "fallbacks": [ModelEntry, ...],
        }

    Examples:
        >>> route_llm("IntentAgent", "classification")
        {"primary": {...nim primary...}, "fallbacks": [{...nim fallback...}, {...openrouter...}]}

        >>> route_llm()   # unknown agent → default route
        {"primary": {...}, "fallbacks": [...]}
    """
    key = (agent_name.lower(), task_type.lower())

    # Exact match first
    models = _ROUTES.get(key)

    # Try (agent_name, "") if task_type not found
    if models is None:
        models = _ROUTES.get((agent_name.lower(), ""))

    # Fall through to default
    if models is None:
        models = _DEFAULT_ROUTE

    return {
        "primary":   models[0],
        "fallbacks": models[1:],
    }