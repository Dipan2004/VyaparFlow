"""
app/core/base_agent.py
----------------------
BaseAgent — the standard interface for all NotiFlow agents.

Every agent in the system inherits from BaseAgent and implements `execute()`.
The public `run()` method provides:
    - unified error handling
    - structured logging into context["history"]
    - state transition on success / failure

Usage
-----
class MyAgent(BaseAgent):
    name = "MyAgent"

    def execute(self, context: dict) -> dict:
        # do work, mutate context, return it
        context["data"]["my_field"] = "value"
        return context

result_ctx = MyAgent().run(context)
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.context import log_step, add_error, update_context
from app.core.event_bus import emit_event

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Abstract base for all NotiFlow agents.

    Subclasses must:
        - Set a class-level ``name`` attribute
        - Implement ``execute(context) -> dict``

    Optional class-level audit declarations (used in history logs):
        input_keys  : list[str]  — context keys this agent reads
        output_keys : list[str]  — context keys this agent writes
        action      : str        — one-line description of what the agent does

    The ``run()`` wrapper handles logging and error isolation automatically.
    Agents should raise exceptions from ``execute()`` on unrecoverable errors;
    for soft/non-fatal issues they should call ``add_error(ctx, msg)`` and
    continue.
    """

    #: Human-readable agent identifier used in logs and history.
    name: str = "BaseAgent"

    #: Audit metadata — override in subclasses for richer logs
    input_keys:  list[str] = []
    output_keys: list[str] = []
    action:      str       = ""

    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the agent with full error handling and audit logging.

        This is the ONLY method callers should invoke externally.

        Args:
            context: The live request context dict.

        Returns:
            The (mutated) context dict.

        Raises:
            Exception: Re-raises any exception from execute() so the
                       orchestrator can decide whether to abort.
        """
        # Emit step started immediately - real-time feedback
        emit_event(
            context,
            "pipeline_step",
            {"step": self.name.lower(), "status": "started", "detail": f"{self.name} started processing"},
            agent=self.name,
            step=self.name.lower(),
            message=f"{self.name} started",
        )

        # Emit log for started state
        emit_event(
            context,
            "log",
            {"step": self.name.lower(), "status": "info", "message": f"[{self.name}] Started processing..."},
            agent=self.name,
            step=self.name.lower(),
            message=f"[{self.name}] Started processing...",
        )

        logger.info("[%s] starting", self.name)
        try:
            context = self.execute(context)
            log_step(
                context,
                self.name,
                "success",
                action      = self.action or f"{self.name} completed",
                input_keys  = list(self.input_keys),
                output_keys = list(self.output_keys),
            )

            # Emit step completed immediately - real-time feedback
            emit_event(
                context,
                "pipeline_step",
                {"step": self.name.lower(), "status": "completed", "detail": f"{self.name} completed successfully"},
                agent=self.name,
                step=self.name.lower(),
                message=f"{self.name} completed",
            )

            # Emit log for completed state
            emit_event(
                context,
                "log",
                {"step": self.name.lower(), "status": "success", "message": f"[{self.name}] Completed successfully"},
                agent=self.name,
                step=self.name.lower(),
                message=f"[{self.name}] Completed successfully",
            )

            logger.info("[%s] completed successfully", self.name)
        except Exception as exc:
            error_msg = f"{self.name} failed: {exc}"
            logger.error(error_msg, exc_info=True)
            add_error(context, error_msg)
            log_step(
                context,
                self.name,
                "error",
                str(exc),
                action      = self.action or f"{self.name} failed",
                input_keys  = list(self.input_keys),
                output_keys = [],
            )

            # Emit step error immediately - real-time feedback
            emit_event(
                context,
                "pipeline_step",
                {"step": self.name.lower(), "status": "failed", "detail": str(exc)},
                agent=self.name,
                step=self.name.lower(),
                message=f"{self.name} failed: {exc}",
            )

            # Emit log for error state
            emit_event(
                context,
                "log",
                {"step": self.name.lower(), "status": "error", "message": f"[{self.name}] Error: {exc}"},
                agent=self.name,
                step=self.name.lower(),
                message=f"[{self.name}] Error: {exc}",
            )

            update_context(context, state="failed")
            raise
        return context

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Agent-specific logic. Subclasses MUST override this method.

        Args:
            context: The live request context dict.

        Returns:
            The mutated context dict.

        Raises:
            NotImplementedError: If subclass does not implement this.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement execute(context)."
        )
