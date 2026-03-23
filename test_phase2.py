"""
test_phase2.py
--------------
Phase 2 tests: Registry, Planner, dynamic Orchestrator, audit logs.

Run with:  python test_phase2.py
No API keys required — all LLM calls are mocked.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("NOTIFLOW_DEMO_MODE", "true")

PASS = "✅"
FAIL = "❌"
_results: list[tuple[str, bool, str]] = []


def test(name: str):
    def decorator(fn):
        try:
            fn()
            _results.append((name, True, ""))
            print(f"  {PASS}  {name}")
        except Exception as exc:
            _results.append((name, False, str(exc)))
            print(f"  {FAIL}  {name}: {exc}")
        return fn
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 1. Agent Registry ────────────────────────────────────────────────")

@test("AGENT_REGISTRY contains all 11 expected agents")
def _():
    from app.core.registry import list_agents
    agents = list_agents()
    required = {
        "intent", "extraction", "validation", "router", "ledger",
        "verification", "monitor", "prediction", "urgency", "escalation", "recovery",
    }
    missing = required - set(agents)
    assert not missing, f"Missing agents: {missing}"


@test("get_agent returns correct agent by key")
def _():
    from app.core.registry import get_agent
    from app.agents.intent_agent import IntentAgent
    agent = get_agent("intent")
    assert isinstance(agent, IntentAgent)


@test("get_agent raises KeyError with helpful message for unknown key")
def _():
    from app.core.registry import get_agent
    try:
        get_agent("nonexistent_agent_xyz")
        assert False, "Should have raised"
    except KeyError as e:
        assert "nonexistent_agent_xyz" in str(e)
        assert "Valid keys" in str(e)


@test("register() adds a new agent to the registry")
def _():
    from app.core.registry import register, get_agent, AGENT_REGISTRY
    from app.core.base_agent import BaseAgent

    class TestAgent(BaseAgent):
        name = "TestAgent"
        def execute(self, ctx):
            ctx["data"]["test"] = True
            return ctx

    register("_test_temp", TestAgent())
    agent = get_agent("_test_temp")
    assert isinstance(agent, TestAgent)
    # Cleanup
    del AGENT_REGISTRY["_test_temp"]


@test("registry agents are singletons (same instance each call)")
def _():
    from app.core.registry import get_agent
    a1 = get_agent("intent")
    a2 = get_agent("intent")
    assert a1 is a2


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 2. Planner — rule evaluation ─────────────────────────────────────")

@test("build_plan returns all 5 steps on fresh context")
def _():
    from app.core.context import create_context
    from app.core.planner import build_plan
    ctx  = create_context("rahul ne 15000 bheja")
    plan = build_plan(ctx)
    keys = [s["agent"] for s in plan]
    assert keys == ["intent", "extraction", "validation", "router", "ledger"], \
        f"Got: {keys}"


@test("build_plan writes plan to context['plan']")
def _():
    from app.core.context import create_context
    from app.core.planner import build_plan
    ctx = create_context("test")
    assert ctx["plan"] == []   # empty before planning
    build_plan(ctx)
    assert len(ctx["plan"]) == 5


@test("build_plan skips 'intent' when intent already set")
def _():
    from app.core.context import create_context, update_context
    from app.core.planner import build_plan
    ctx = create_context("test")
    update_context(ctx, intent="payment")
    plan = build_plan(ctx)
    agent_keys = [s["agent"] for s in plan]
    assert "intent" not in agent_keys, f"'intent' should be skipped but got: {agent_keys}"
    assert "extraction" in agent_keys


@test("build_plan skips 'extraction' when data already populated")
def _():
    from app.core.context import create_context, update_context
    from app.core.planner import build_plan
    ctx = create_context("test")
    update_context(ctx, intent="payment", data={"customer": "Rahul", "amount": 500})
    plan = build_plan(ctx)
    agent_keys = [s["agent"] for s in plan]
    assert "extraction" not in agent_keys
    assert "validation" in agent_keys


@test("build_plan skips 'router' when event already populated")
def _():
    from app.core.context import create_context, update_context
    from app.core.planner import build_plan
    ctx = create_context("test")
    update_context(ctx,
        intent="payment",
        data={"customer": "Rahul"},
        event={"event": "payment_recorded"},
        state="validated",
    )
    plan = build_plan(ctx)
    agent_keys = [s["agent"] for s in plan]
    assert "router" not in agent_keys
    assert "ledger" in agent_keys   # ledger always runs


@test("build_plan always includes 'ledger' (even on fully pre-populated context)")
def _():
    from app.core.context import create_context, update_context
    from app.core.planner import build_plan
    ctx = create_context("test")
    update_context(ctx,
        intent="payment",
        data={"customer": "X"},
        event={"event": "payment_recorded"},
        state="validated",
    )
    plan = build_plan(ctx)
    agent_keys = [s["agent"] for s in plan]
    assert "ledger" in agent_keys


@test("plan steps have correct 'critical' flags")
def _():
    from app.core.context import create_context
    from app.core.planner import build_plan
    ctx  = create_context("test")
    plan = build_plan(ctx)
    by_agent = {s["agent"]: s for s in plan}
    # All core steps are critical
    for key in ("intent", "extraction", "validation", "router"):
        assert by_agent[key]["critical"] is True, f"{key} should be critical"
    # Ledger is non-critical
    assert by_agent["ledger"]["critical"] is False


@test("plan steps have 'description' field")
def _():
    from app.core.context import create_context
    from app.core.planner import build_plan
    ctx  = create_context("test")
    plan = build_plan(ctx)
    for step in plan:
        assert step.get("description"), f"Step '{step['agent']}' missing description"


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 3. Dynamic Orchestrator ──────────────────────────────────────────")

def _mock_llms(intent_resp, extract_resp):
    """Helper: returns (intent_mock, extract_mock) pair."""
    im = MagicMock(); im.generate.return_value = intent_resp
    em = MagicMock(); em.generate.return_value = extract_resp
    return im, em


@test("Orchestrator executes all 5 plan steps on a fresh payment message")
def _():
    import pandas as pd
    from app.core.orchestrator import process_message
    im, em = _mock_llms(
        '{"intent":"payment"}',
        json.dumps({"customer": "Rahul", "amount": 15000, "payment_type": None}),
    )
    with patch("app.agents.intent_agent.get_llm",     return_value=im), \
         patch("app.agents.extraction_agent.get_llm", return_value=em), \
         patch("app.utils.excel_writer.append_row"), \
         patch("app.utils.excel_writer.read_sheet",   return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service._get_sheet", return_value=None):
        result = process_message("rahul ne 15000 bheja")

    ctx    = result["context"]
    agents = [h["agent"] for h in ctx["history"]]
    assert "IntentAgent"      in agents
    assert "ExtractionAgent"  in agents
    assert "ValidationAgent"  in agents
    assert "SkillRouterAgent" in agents
    assert "LedgerAgent"      in agents
    assert ctx["state"] == "completed"


@test("Orchestrator skips IntentAgent when intent pre-set in context")
def _():
    import pandas as pd
    from app.core.context    import create_context, update_context
    from app.core.planner    import build_plan
    from app.core.registry   import get_agent

    ctx = create_context("already classified")
    update_context(ctx, intent="payment")
    plan = build_plan(ctx)
    agent_keys = [s["agent"] for s in plan]
    assert "intent" not in agent_keys
    assert "extraction" in agent_keys


@test("Orchestrator plan is driven entirely by planner (no static list)")
def _():
    """Verify orchestrator.py contains no _PIPELINE or _FINAL references."""
    import inspect
    from app.core import orchestrator
    src = inspect.getsource(orchestrator)
    assert "_PIPELINE" not in src, "_PIPELINE should not exist in new orchestrator"
    assert "_FINAL"    not in src, "_FINAL should not exist in new orchestrator"


@test("Non-critical agent failure does not abort pipeline")
def _():
    import pandas as pd
    from app.core.orchestrator import process_message
    im, em = _mock_llms(
        '{"intent":"payment"}',
        json.dumps({"customer": "Test", "amount": 100, "payment_type": None}),
    )
    with patch("app.agents.intent_agent.get_llm",     return_value=im), \
         patch("app.agents.extraction_agent.get_llm", return_value=em), \
         patch("app.utils.excel_writer.append_row"), \
         patch("app.utils.excel_writer.read_sheet",   return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service.append_transaction",
               side_effect=Exception("Sheets exploded")):
        result = process_message("test 100 bheja")

    # Pipeline completed despite ledger failure
    assert result["context"]["state"] == "completed"
    assert result["sheet_updated"] is False
    # LedgerAgent must appear in history — execute() swallows the error
    agents = [h["agent"] for h in result["context"]["history"]]
    assert "LedgerAgent" in agents
    # Error recorded in context errors list
    assert any("LedgerAgent" in e for e in result["context"]["errors"])


@test("Missing agent in registry is handled gracefully (non-critical)")
def _():
    from app.core.context  import create_context
    from app.core.planner  import build_plan, _RULES
    from app.core.registry import AGENT_REGISTRY, _ensure_init
    from app.core.orchestrator import process_message
    import pandas as pd

    # Temporarily inject a plan step pointing to a non-existent agent
    from app.core import planner as _planner
    from app.core.planner import PlanRule

    fake_rule = PlanRule(
        agent="ghost_agent_xyz",
        condition=lambda ctx: True,
        critical=False,
        description="Test ghost agent",
    )
    _planner._RULES.append(fake_rule)

    im, em = _mock_llms(
        '{"intent":"payment"}',
        json.dumps({"customer": "X", "amount": 1, "payment_type": None}),
    )
    try:
        with patch("app.agents.intent_agent.get_llm",     return_value=im), \
             patch("app.agents.extraction_agent.get_llm", return_value=em), \
             patch("app.utils.excel_writer.append_row"), \
             patch("app.utils.excel_writer.read_sheet",   return_value=pd.DataFrame()), \
             patch("app.services.google_sheets_service._get_sheet", return_value=None):
            result = process_message("x bheja")
        # Pipeline should still complete
        assert result["context"]["state"] == "completed"
        # Error should be recorded
        assert any("ghost_agent_xyz" in e for e in result["context"]["errors"])
    finally:
        _planner._RULES.remove(fake_rule)


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 4. Audit-ready history entries ───────────────────────────────────")

@test("History entries have all 7 required audit fields")
def _():
    import pandas as pd
    from app.core.orchestrator import process_message
    im, em = _mock_llms(
        '{"intent":"order"}',
        json.dumps({"customer": None, "item": "kurti", "quantity": 3}),
    )
    with patch("app.agents.intent_agent.get_llm",     return_value=im), \
         patch("app.agents.extraction_agent.get_llm", return_value=em), \
         patch("app.utils.excel_writer.append_row"), \
         patch("app.utils.excel_writer.read_sheet",   return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service._get_sheet", return_value=None):
        result = process_message("3 kurti bhej dena")

    required_fields = {"agent", "action", "input_keys", "output_keys",
                       "status", "detail", "timestamp"}
    for entry in result["context"]["history"]:
        missing = required_fields - set(entry.keys())
        assert not missing, f"History entry missing fields: {missing}\n  entry={entry}"


@test("IntentAgent history entry has correct input/output keys")
def _():
    import pandas as pd
    from app.core.orchestrator import process_message
    im, em = _mock_llms(
        '{"intent":"payment"}',
        json.dumps({"customer": "Rahul", "amount": 5000, "payment_type": "cash"}),
    )
    with patch("app.agents.intent_agent.get_llm",     return_value=im), \
         patch("app.agents.extraction_agent.get_llm", return_value=em), \
         patch("app.utils.excel_writer.append_row"), \
         patch("app.utils.excel_writer.read_sheet",   return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service._get_sheet", return_value=None):
        result = process_message("rahul ne 5000 bheja")

    history = {h["agent"]: h for h in result["context"]["history"]}
    intent_entry = history["IntentAgent"]
    assert "message" in intent_entry["input_keys"]
    assert "intent"  in intent_entry["output_keys"]
    assert intent_entry["status"] == "success"


@test("All history entries have ISO-8601 timestamps")
def _():
    import re, pandas as pd
    from app.core.orchestrator import process_message
    im, em = _mock_llms(
        '{"intent":"order"}',
        json.dumps({"customer": None, "item": "aata", "quantity": 2}),
    )
    with patch("app.agents.intent_agent.get_llm",     return_value=im), \
         patch("app.agents.extraction_agent.get_llm", return_value=em), \
         patch("app.utils.excel_writer.append_row"), \
         patch("app.utils.excel_writer.read_sheet",   return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service._get_sheet", return_value=None):
        result = process_message("2 aata bhej dena")

    iso_pattern = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
    for entry in result["context"]["history"]:
        ts = entry.get("timestamp", "")
        assert iso_pattern.match(ts), f"Bad timestamp: {ts!r}"


@test("log_step backward compat: old 4-arg call still works")
def _():
    from app.core.context import create_context, log_step
    ctx = create_context("x")
    # Old call style — must not raise
    log_step(ctx, "OldAgent", "success", "some detail")
    entry = ctx["history"][0]
    assert entry["agent"]  == "OldAgent"
    assert entry["status"] == "success"
    assert entry["detail"] == "some detail"
    # New fields have sensible defaults
    assert entry["input_keys"]  == []
    assert entry["output_keys"] == []
    assert "action" in entry


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 5. Extensibility — adding a custom agent ─────────────────────────")

@test("Custom agent registered + added to planner executes in pipeline")
def _():
    import pandas as pd
    from app.core.base_agent import BaseAgent
    from app.core.registry   import register, AGENT_REGISTRY
    from app.core import planner as _planner
    from app.core.planner    import PlanRule
    from app.core.orchestrator import process_message

    # Define a new agent
    class PriorityAgent(BaseAgent):
        name        = "PriorityAgent"
        input_keys  = ["intent"]
        output_keys = ["priority"]
        action      = "Set request priority based on intent"

        def execute(self, ctx):
            ctx["priority"] = "high" if ctx.get("intent") == "payment" else "normal"
            return ctx

    # Register it
    register("priority", PriorityAgent())

    # Add a planner rule (after validation, before routing)
    new_rule = PlanRule(
        agent       = "priority",
        condition   = lambda ctx: True,
        critical    = False,
        description = "Classify request priority",
    )
    insert_at = next(
        (i for i, r in enumerate(_planner._RULES) if r.agent == "router"), 3
    )
    _planner._RULES.insert(insert_at, new_rule)

    im, em = _mock_llms(
        '{"intent":"payment"}',
        json.dumps({"customer": "Amit", "amount": 8000, "payment_type": "upi"}),
    )
    try:
        with patch("app.agents.intent_agent.get_llm",     return_value=im), \
             patch("app.agents.extraction_agent.get_llm", return_value=em), \
             patch("app.utils.excel_writer.append_row"), \
             patch("app.utils.excel_writer.read_sheet",   return_value=pd.DataFrame()), \
             patch("app.services.google_sheets_service._get_sheet", return_value=None):
            result = process_message("amit ne 8000 gpay bheja")

        # PriorityAgent ran and appears in history
        agents_ran = [h["agent"] for h in result["context"]["history"]]
        assert "PriorityAgent" in agents_ran, f"PriorityAgent not in history: {agents_ran}"
        # PriorityAgent's history entry was successful
        priority_entry = next(h for h in result["context"]["history"] if h["agent"] == "PriorityAgent")
        assert priority_entry["status"] == "success"
        # priority key exists in context (UrgencyAgent may have updated it after)
        assert result["context"]["priority"] in ("high", "normal", "critical", "low")
    finally:
        _planner._RULES.remove(new_rule)
        del AGENT_REGISTRY["priority"]


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 6. Backward compatibility ────────────────────────────────────────")

@test("Public API response shape contains all expected keys")
def _():
    import pandas as pd
    from app.core.orchestrator import process_message
    im, em = _mock_llms(
        '{"intent":"credit"}',
        json.dumps({"customer": "Suresh", "item": "goods",
                    "quantity": None, "amount": 500}),
    )
    with patch("app.agents.intent_agent.get_llm",     return_value=im), \
         patch("app.agents.extraction_agent.get_llm", return_value=em), \
         patch("app.utils.excel_writer.append_row"), \
         patch("app.utils.excel_writer.read_sheet",   return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service._get_sheet", return_value=None):
        result = process_message("suresh ko 500 udhar dena")

    # Phase 1 core keys must still be present
    core_keys = {"message", "intent", "data", "event", "sheet_updated", "context"}
    # Phase 3 autonomy keys now also present
    autonomy_keys = {"verification", "risk", "priority", "alerts", "recovery", "monitor"}
    required = core_keys | autonomy_keys
    missing = required - set(result.keys())
    assert not missing, f"Missing keys: {missing}"
    assert result["intent"] == "credit"
    assert result["data"]["customer"] == "Suresh"
    assert result["event"]["event"] == "credit_recorded"
    # Autonomy fields are populated
    assert "status" in result["verification"]
    assert "level"  in result["risk"]


@test("run_notiflow() demo mode still returns same shape (no context key)")
def _():
    from app.main import run_notiflow
    result = run_notiflow("rahul ne 15000 bheja", demo_mode=True)
    required = {"message", "intent", "data", "event", "sheet_updated"}
    for key in required:
        assert key in result, f"Missing key: {key}"


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
total  = len(_results)
passed = sum(1 for _, ok, _ in _results if ok)
failed = total - passed

print(f"\n{'─'*60}")
print(f"  Results: {passed}/{total} passed", end="")
if failed:
    print(f"  ({failed} failed)")
    for name, ok, err in _results:
        if not ok:
            print(f"    {FAIL}  {name}")
            print(f"         {err}")
else:
    print("  — all green ✅")
print(f"{'─'*60}\n")

sys.exit(0 if failed == 0 else 1)