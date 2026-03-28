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

_NIM_API_KEY        = os.getenv("NVIDIA_NIM_API_KEY") or os.getenv("NVIDIA_API_KEY")
_NIM_BASE_URL       = (
    os.getenv("NVIDIA_NIM_BASE_URL")
    or os.getenv("NIM_BASE_URL")
    or "https://integrate.api.nvidia.com/v1"
)
_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
_OPENROUTER_BASE    = "https://openrouter.ai/api/v1"
_LEGACY_NIM_MODEL   = os.getenv("NVIDIA_NIM_MODEL", "deepseek-ai/deepseek-v3.2")
_REQUEST_TIMEOUT_S  = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
_RETRY_COUNT        = int(os.getenv("LLM_RETRY_COUNT", "2"))
_SIMULATE_NIM_FAILURE = os.getenv("SIMULATE_NIM_FAILURE", "false").lower() == "true"
_SIMULATED_NIM_FAILURE_USED = False
_SIMULATE_NIM_FAIL  = os.getenv("SIMULATE_NIM_FAILURE", "false").lower() == "true"


# ---------------------------------------------------------------------------
# LLMService
# ---------------------------------------------------------------------------

class LLMService:
    """
    Single entry point for all LLM inference in NotiFlow.

    Phase 4: routes per agent/task, iterates fallbacks automatically,
    optionally writes audit info to context.
    """

    def call_llm(
        self,
        prompt: str,
        agent_name: str,
        *,
        max_tokens: int = 256,
        task_type: str = "",
        context: Optional[dict[str, Any]] = None,
        stream: bool = False,
    ) -> str:
        """Convenience wrapper for agent-aware LLM calls."""
        return self.generate(
            prompt,
            max_tokens=max_tokens,
            agent_name=agent_name,
            task_type=task_type,
            context=context,
            stream=stream,
        )

    def generate(
        self,
        prompt:     str,
        max_tokens: int = 256,
        *,
        agent_name: str = "",
        task_type:  str = "",
        context:    Optional[dict[str, Any]] = None,
        stream:     bool = False,
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
        from app.core.event_bus import emit_event

        route      = route_llm(agent_name, task_type)
        primary    = route["primary"]
        fallbacks  = route["fallbacks"]
        all_models = [primary] + fallbacks
        self._stream_requested = stream

        if context is not None:
            context.setdefault("metadata", {}).update({
                "llm_timeout_seconds": _REQUEST_TIMEOUT_S,
                "llm_retry_count": _RETRY_COUNT,
                "llm_stream": stream,
            })

        last_exc: Optional[Exception] = None
        tried: list[str] = []

        for idx, model_entry in enumerate(all_models):
            provider   = model_entry["provider"]
            model_name = model_entry["model"]
            tokens     = model_entry.get("max_tokens") or max_tokens

            # ── Error Simulation: NIM failure ─────────────────────────────
            if _SIMULATE_NIM_FAIL and provider == "nim" and "v3.2" in model_name:
                logger.warning(f"SIMULATION: Intentional NIM timeout for {model_name}")
                exc = RuntimeError(f"NIM gateway timeout (simulated) for {model_name}")
                tried.append(model_name)
                last_exc = exc
                next_model = all_models[idx + 1] if idx + 1 < len(all_models) else None
                if context is not None:
                    emit_event(
                        context,
                        "error_occurred",
                        {
                            "step": agent_name or "llm",
                            "message": str(exc),
                            "provider": provider,
                            "model": model_name,
                        },
                        agent=agent_name or "LLMService",
                        step="llm",
                        message=str(exc),
                        status="error",
                    )
                    if next_model is not None:
                        emit_event(
                            context,
                            "recovery_triggered",
                            {
                                "step": agent_name or "llm",
                                "failed_provider": provider,
                                "failed_model": model_name,
                                "fallback_provider": next_model.get("provider"),
                                "fallback_model": next_model.get("model"),
                            },
                            agent=agent_name or "LLMService",
                            step="llm",
                            message=f"Fallback triggered → {next_model.get('provider')}/{next_model.get('model')}",
                        )
                self._log_fallback(agent_name, provider, model_name, exc, next_model)
                continue

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
                    if idx > 0:
                        emit_event(
                            context,
                            "recovery_success",
                            {
                                "step": agent_name or "llm",
                                "provider": provider,
                                "model": model_name,
                                "models_tried": tried + [model_name],
                            },
                            agent=agent_name or "LLMService",
                            step="llm",
                            message=f"Recovered with {provider}/{model_name}",
                        )

                level = "primary" if idx == 0 else f"fallback #{idx}"
                logger.info(
                    "LLMService → %s/%s (%s, agent=%s)",
                    provider, model_name, level, agent_name or "unknown"
                )
                return response

            except Exception as exc:
                tried.append(model_name)
                last_exc = exc
                next_model = all_models[idx + 1] if idx + 1 < len(all_models) else None
                if context is not None:
                    emit_event(
                        context,
                        "error_occurred",
                        {
                            "step": agent_name or "llm",
                            "message": str(exc),
                            "provider": provider,
                            "model": model_name,
                        },
                        agent=agent_name or "LLMService",
                        step="llm",
                        message=str(exc),
                    )
                    if next_model is not None:
                        emit_event(
                            context,
                            "recovery_triggered",
                            {
                                "step": agent_name or "llm",
                                "failed_provider": provider,
                                "failed_model": model_name,
                                "fallback_provider": next_model.get("provider"),
                                "fallback_model": next_model.get("model"),
                            },
                            agent=agent_name or "LLMService",
                            step="llm",
                            message=f"Fallback to {next_model.get('provider')}/{next_model.get('model')}",
                        )
                self._log_fallback(agent_name, provider, model_name, exc, next_model)
                continue

        if not agent_name and not task_type:
            try:
                logger.warning("[LLMService] route exhausted - using legacy Gemini shim")
                response = self._call_gemini(prompt)
                if context is not None:
                    context["model_used"] = "gemini-legacy"
                    context["fallback_used"] = True
                    context.setdefault("metadata", {}).update({
                        "model_used": "gemini-legacy",
                        "model_provider": "gemini",
                        "fallback_used": True,
                        "models_tried": tried + ["gemini-legacy"],
                    })
                return response
            except Exception as gemini_exc:
                last_exc = gemini_exc
                tried.append("gemini-legacy")

        logger.error("LLMService: all %d model(s) failed. Last: %s", len(tried), last_exc)
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
        global _SIMULATED_NIM_FAILURE_USED
        if _SIMULATE_NIM_FAILURE and not _SIMULATED_NIM_FAILURE_USED:
            _SIMULATED_NIM_FAILURE_USED = True
            raise TimeoutError("NIM timeout")
        if not _NIM_API_KEY:
            raise RuntimeError("NVIDIA_NIM_API_KEY is not set.")
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai not installed. Run: pip install openai")

        client = OpenAI(
            base_url=_NIM_BASE_URL,
            api_key=_NIM_API_KEY,
            timeout=_REQUEST_TIMEOUT_S,
            max_retries=0,
        )
        text = self._request_with_retry(
            provider_label=f"NIM[{model_name}]",
            request_fn=lambda: self._create_chat_completion(client, model_name, prompt, max_tokens),
        )
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
            timeout=_REQUEST_TIMEOUT_S,
            max_retries=0,
        )
        text = self._request_with_retry(
            provider_label=f"OpenRouter[{model_name}]",
            request_fn=lambda: self._create_chat_completion(client, model_name, prompt, max_tokens),
        )
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

    def _create_chat_completion(self, client: Any, model_name: str, prompt: str, max_tokens: int) -> str:
        completion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=max_tokens,
            stream=getattr(self, "_stream_requested", False),
        )
        if getattr(self, "_stream_requested", False):
            chunks: list[str] = []
            for event in completion:
                if not getattr(event, "choices", None):
                    continue
                delta = getattr(event.choices[0].delta, "content", None)
                if delta:
                    chunks.append(delta)
            return "".join(chunks)
        return completion.choices[0].message.content or ""

    def _request_with_retry(self, provider_label: str, request_fn: Any) -> str:
        last_exc: Optional[Exception] = None
        for attempt in range(_RETRY_COUNT + 1):
            try:
                return request_fn()
            except Exception as exc:
                last_exc = exc
                if attempt >= _RETRY_COUNT:
                    break
                logger.warning(
                    "%s request failed (%s) - retry %d/%d",
                    provider_label,
                    exc,
                    attempt + 1,
                    _RETRY_COUNT,
                )
        raise last_exc if last_exc is not None else RuntimeError(f"{provider_label} failed")

    def _log_fallback(
        self,
        agent_name: str,
        provider: str,
        model_name: str,
        exc: Exception,
        next_model: Optional[dict[str, Any]],
    ) -> None:
        agent_label = agent_name or "LLMService"
        failure_kind = "timeout" if self._is_timeout_error(exc) else "error"
        if next_model is None:
            logger.error(
                "[%s] %s %s on %s - no fallback remaining",
                agent_label,
                self._provider_label(provider),
                failure_kind,
                model_name,
            )
            return
        logger.warning(
            "[%s] %s %s - fallback %s",
            agent_label,
            self._provider_label(provider),
            failure_kind,
            self._fallback_target_label(next_model),
        )

    @staticmethod
    def _provider_label(provider: str) -> str:
        return "NIM" if provider == "nim" else "OpenRouter"

    def _fallback_target_label(self, model_entry: dict[str, Any]) -> str:
        provider = model_entry.get("provider", "")
        model_name = str(model_entry.get("model", ""))
        if provider == "openrouter":
            return "OpenRouter"
        if provider == "nim" and "v3.1" in model_name:
            return "v3.1"
        if provider == "nim" and "v3.2" in model_name:
            return "v3.2"
        return model_name or self._provider_label(provider)

    @staticmethod
    def _is_timeout_error(exc: Exception) -> bool:
        name = exc.__class__.__name__.lower()
        text = str(exc).lower()
        return "timeout" in name or "timeout" in text or "timed out" in text


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
