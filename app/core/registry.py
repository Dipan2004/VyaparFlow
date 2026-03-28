"""
app/core/registry.py
--------------------
Agent Registry for NotiFlow Autonomous.

Single source of truth for all registered agents.
The orchestrator resolves agent names from this registry — it never
imports agent classes directly.

Extending the system
--------------------
To add a new agent:
    1. Create app/agents/my_agent.py (subclass BaseAgent)
    2. Add one line here:  "my_agent": MyAgent()

That's it. The planner and orchestrator pick it up automatically as
long as the planner emits the agent's key in a plan step.

Public API
----------
AGENT_REGISTRY : dict[str, BaseAgent]
    The live registry dict. Import and use directly.

get_agent(name) -> BaseAgent
    Safe accessor — raises KeyError with a helpful message if missing.

register(name, agent) -> None
    Runtime registration (useful for plugins / tests).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.base_agent import BaseAgent

# ---------------------------------------------------------------------------
# Lazy imports — prevents circular import chains at module load time
# ---------------------------------------------------------------------------

def _build_registry() -> dict[str, "BaseAgent"]:
    from app.agents.intent_agent        import IntentAgent
    from app.agents.extraction_agent    import ExtractionAgent
    from app.agents.validation_agent    import ValidationAgent
    from app.agents.invoice_agent       import InvoiceAgent
    from app.agents.payment_agent       import PaymentAgent
    from app.agents.skill_router_agent  import SkillRouterAgent
    from app.agents.ledger_agent        import LedgerAgent
    # ── Phase 3: Autonomy Layer ──────────────────────────────────────────────
    from app.agents.verification_agent  import VerificationAgent
    from app.agents.monitor_agent       import MonitorAgent
    from app.agents.prediction_agent    import PredictionAgent
    from app.agents.urgency_agent       import UrgencyAgent
    from app.agents.escalation_agent    import EscalationAgent
    from app.agents.recovery_agent      import RecoveryAgent

    return {
        # Core pipeline agents
        "intent":       IntentAgent(),
        "extraction":   ExtractionAgent(),
        "validation":   ValidationAgent(),
        "invoice_agent": InvoiceAgent(),
        "payment_agent": PaymentAgent(),
        "router":       SkillRouterAgent(),
        "ledger":       LedgerAgent(),
        # Autonomy layer agents
        "verification": VerificationAgent(),
        "monitor":      MonitorAgent(),
        "prediction":   PredictionAgent(),
        "urgency":      UrgencyAgent(),
        "escalation":   EscalationAgent(),
        "recovery":     RecoveryAgent(),
    }


# Module-level registry — built once on first access via get_agent()
# Direct dict access also works: AGENT_REGISTRY["intent"]
AGENT_REGISTRY: dict[str, "BaseAgent"] = {}

_initialised = False


def _ensure_init() -> None:
    global _initialised
    if not _initialised:
        AGENT_REGISTRY.update(_build_registry())
        _initialised = True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_agent(name: str) -> "BaseAgent":
    """
    Retrieve an agent by registry key.

    Args:
        name: Agent key (e.g. "intent", "extraction", "ledger").

    Returns:
        The registered BaseAgent instance.

    Raises:
        KeyError: If no agent is registered under that name, with a
                  helpful message listing valid keys.
    """
    _ensure_init()
    if name not in AGENT_REGISTRY:
        valid = ", ".join(sorted(AGENT_REGISTRY.keys()))
        raise KeyError(
            f"No agent registered as '{name}'. "
            f"Valid keys: {valid}"
        )
    return AGENT_REGISTRY[name]


def register(name: str, agent: "BaseAgent") -> None:
    """
    Register a new agent (or replace an existing one) at runtime.

    Useful for plugins, testing, and dynamic skill agents.

    Args:
        name:  Registry key (e.g. "my_custom_agent").
        agent: Instantiated BaseAgent subclass.
    """
    _ensure_init()
    AGENT_REGISTRY[name] = agent


def list_agents() -> list[str]:
    """Return sorted list of all registered agent keys."""
    _ensure_init()
    return sorted(AGENT_REGISTRY.keys())
