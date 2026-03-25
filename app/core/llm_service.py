"""
app/core/llm_service.py
-----------------------
Unified LLM Service for NotiFlow Autonomous — Phase 4.

ALL LLM calls in the system go through this single service.
No other module is allowed to call an LLM API directly.

Phase 4 additions
-----------------
* generate() accepts optional agent_name + task_type kwargs
* Internally calls llm_router.route_llm() to get ordered model list
* Iterates primary → fallback-1 → fallback-2 until one succeeds
* Writes model_used / fallback_used into context if passed
* Supports NVIDIA NIM and OpenRouter (both OpenAI-compatible)

Backward compatibility
----------------------
generate(prompt)                    — still works, uses default routing
generate(prompt, max_tokens=256)    — still works
generate(prompt, agent_name="intent", task_type="classification")  — Phase 4

Configuration (.env)
--------------------
NVIDIA_NIM_API_KEY     — NIM primary key
NVIDIA_NIM_BASE_URL    — default: https://integrate.api.nvidia.com/v1
NIM_PRIMARY_MODEL      — default: deepseek-ai/deepseek-v3
NIM_FALLBACK_MODEL     — default: deepseek-ai/deepseek-r1
OPENROUTER_API_KEY     — OpenRouter fallback key
OPENROUTER_MODEL       — default: deepseek/deepseek-chat

Public API
----------
LLMService().generate(prompt, max_tokens, agent_name, task_type, context) -> str
get_llm() -> LLMService
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_NIM_API_KEY        = os.getenv("NVIDIA_NIM_API_KEY")
_NIM_BASE_URL       = os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
_OPENROUTER_BASE    = "https://openrouter.ai/api/v1"
_LEGACY_NIM_MODEL   = os.getenv("NVIDIA_NIM_MODEL", "deepseek-ai/deepseek-v3")


# ---------------------------------------------------------------------------
# LLMService
# ---------------------------------------------------------------------------

class LLMService:
    """
    Single entry point for all LLM inference in NotiFlow.

    Phase 4: routes per agent/task, iterates fallbacks automatically,
    optionally writes audit info to context.
    """

    def generate(
        self,
        prompt:     str,
        max_tokens: int = 256,
        *,
        agent_name: str = "",
        task_type:  str = "",
        context:    Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Send a prompt to the best available model for this agent/task.

        Args:
            prompt:     Fully rendered prompt string.
            max_tokens: Maximum tokens to generate (default 256).
            agent_name: Calling agent class name — used by router.
            task_type:  Task category — used by router.
            context:    Optional live context dict.  If provided, writes
                        context["model_used"] and context["fallback_used"].

        Returns:
            Raw text response (JSON or plain text — callers parse it).

        Raises:
            RuntimeError: If ALL models in the route fail.
        """
        from app.core.llm_router import route_llm

        route      = route_llm(agent_name, task_type)
        primary    = route["primary"]
        fallbacks  = route["fallbacks"]
        all_models = [primary] + fallbacks

        last_exc: Optional[Exception] = None
        tried: list[str] = []

        for idx, model_entry in enumerate(all_models):
            provider   = model_entry["provider"]
            model_name = model_entry["model"]
            tokens     = model_entry.get("max_tokens") or max_tokens

            try:
                response = self._call_model(provider, model_name, prompt, tokens)

                # ── Write audit info to context ───────────────────────────
                if context is not None:
                    context["model_used"]    = model_name
                    context["fallback_used"] = idx > 0
                    context.setdefault("metadata", {}).update({
                        "model_used":     model_name,
                        "model_provider": provider,
                        "fallback_used":  idx > 0,
                        "models_tried":   tried + [model_name],
                    })

                level = "primary" if idx == 0 else f"fallback #{idx}"
                logger.info(
                    "LLMService → %s/%s (%s, agent=%s)",
                    provider, model_name, level, agent_name or "unknown"
                )
                return response

            except Exception as exc:
                tried.append(model_name)
                last_exc = exc
                logger.warning(
                    "LLMService: %s/%s failed (%s) — trying next",
                    provider, model_name, exc
                )
                continue

        logger.error("LLMService: all %d model(s) failed. Last: %s", len(all_models), last_exc)
        raise RuntimeError(
            f"All LLM backends failed for agent='{agent_name}' task='{task_type}'. "
            f"Tried: {tried}. Last error: {last_exc}"
        ) from last_exc

    # ── Model dispatch ────────────────────────────────────────────────────────

    def _call_model(self, provider: str, model_name: str, prompt: str, max_tokens: int) -> str:
        if provider == "nim":
            return self._call_nim(model_name, prompt, max_tokens)
        elif provider == "openrouter":
            return self._call_openrouter(model_name, prompt, max_tokens)
        else:
            raise RuntimeError(f"Unknown LLM provider: '{provider}'")

    # ── NVIDIA NIM ────────────────────────────────────────────────────────────

    def _call_nim(self, model_name: str, prompt: str, max_tokens: int) -> str:
        if not _NIM_API_KEY:
            raise RuntimeError("NVIDIA_NIM_API_KEY is not set.")
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")

        client = OpenAI(base_url=_NIM_BASE_URL, api_key=_NIM_API_KEY)
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        text = completion.choices[0].message.content or ""
        logger.debug("NIM[%s] raw: %r", model_name, text[:200])
        return text.strip()

    # ── OpenRouter ────────────────────────────────────────────────────────────

    def _call_openrouter(self, model_name: str, prompt: str, max_tokens: int) -> str:
        if not _OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY is not set.")
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")

        extra_headers = {"X-Title": os.getenv("OPENROUTER_TITLE", "NotiFlow")}
        referer = os.getenv("OPENROUTER_REFERER")
        if referer:
            extra_headers["HTTP-Referer"] = referer

        client = OpenAI(
            base_url=_OPENROUTER_BASE,
            api_key=_OPENROUTER_API_KEY,
            default_headers=extra_headers,
        )
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        text = completion.choices[0].message.content or ""
        logger.debug("OpenRouter[%s] raw: %r", model_name, text[:200])
        return text.strip()

    # ── Legacy shims — test_pipeline.py patches these directly ───────────────
    # DO NOT rename or remove — existing tests mock them by name.

    def _call_gemini(self, prompt: str) -> str:
        """Gemini shim — kept for test_pipeline.py backward compat."""
        try:
            from app.services.gemini_client import generate
        except ImportError:
            from app.services.gemini_client import generate  # type: ignore
        return generate(prompt)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_instance: Optional[LLMService] = None


def get_llm() -> LLMService:
    """Return the shared LLMService singleton."""
    global _instance
    if _instance is None:
        _instance = LLMService()
    return _instance