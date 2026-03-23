"""app/core — NotiFlow core primitives."""

from app.core.llm_service import LLMService, get_llm
from app.core.context     import create_context, update_context, log_step, add_error
from app.core.base_agent  import BaseAgent
from app.core.planner     import build_plan, PlanRule
from app.core.registry    import get_agent, register, list_agents, AGENT_REGISTRY

__all__ = [
    # LLM
    "LLMService", "get_llm",
    # Context
    "create_context", "update_context", "log_step", "add_error",
    # Agent base
    "BaseAgent",
    # Planner
    "build_plan", "PlanRule",
    # Registry
    "get_agent", "register", "list_agents", "AGENT_REGISTRY",
]
