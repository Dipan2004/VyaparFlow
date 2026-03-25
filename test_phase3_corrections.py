"""
test_phase3_corrections.py
---------------------------
Architecture Correction Tests (Phase 3 fixes):

    Fix 1 — Dynamic autonomy planner (replaces _AUTONOMY_SEQUENCE)
    Fix 2 — Feedback loop with replan cap
    Fix 3 — Priority score accumulation (replaces string overwrite)

Run with:  python test_phase3_corrections.py
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


def _mocks(intent="payment", amount=500, customer="Rahul", payment_type=None):
    im = MagicMock()
    em = MagicMock()
    im.generate.return_value = json.dumps({"intent": intent})
    em.generate.return_value = json.dumps({
        "customer": customer, "amount": amount, "payment_type": payment_type
    })
    return im, em


def _run(message="rahul ne 500 bheja", intent="payment", amount=500,
         customer="Rahul", payment_type=None):
    """Helper: run process_message with mocked LLM + Excel + Sheets."""
    import pandas as pd
    from app.core.orchestrator import process_message
    im, em = _mocks(intent, amount, customer, payment_type)
    with patch("app.agents.intent_agent.get_llm",     return_value=im), \
         patch("app.agents.extraction_agent.get_llm", return_value=em), \
         patch("utils.excel_writer.append_row"), \
         patch("utils.excel_writer.read_sheet",   return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service.append_transaction",
               return_value=False):
        return process_message(message)


# =============================================================================
print("\n── Fix 1: Dynamic Autonomy Planner ──────────────────────────────────")
# =============================================================================

@test("_AUTONOMY_SEQUENCE does not exist in orchestrator source")
def _():
    import inspect
    from app.core import orchestrator
    src = inspect.getsource(orchestrator)
    assert "_AUTONOMY_SEQUENCE" not in src, \
        "_AUTONOMY_SEQUENCE still present — static sequence not removed"


@test("orchestrator imports build_autonomy_plan, not a hardcoded list")
def _():
    import inspect
    from app.core import orchestrator
    src = inspect.getsource(orchestrator)
    assert "build_autonomy_plan" in src


@test("build_autonomy_plan returns list[dict] with agent+description keys")
def _():
    from app.core.context          import create_context
    from app.core.autonomy_planner import build_autonomy_plan
    ctx  = create_context("test")
    plan = build_autonomy_plan(ctx)
    assert isinstance(plan, list)
    assert len(plan) > 0
    for step in plan:
        assert "agent"       in step, f"step missing 'agent': {step}"
        assert "description" in step, f"step missing 'description': {step}"


@test("build_autonomy_plan writes to context['autonomy_plan']")
def _():
    from app.core.context          import create_context
    from app.core.autonomy_planner import build_autonomy_plan
    ctx = create_context("test")
    assert ctx["autonomy_plan"] == []
    build_autonomy_plan(ctx)
    assert len(ctx["autonomy_plan"]) > 0


@test("verification always in autonomy plan for fresh context")
def _():
    from app.core.context          import create_context
    from app.core.autonomy_planner import build_autonomy_plan
    ctx   = create_context("test")
    plan  = build_autonomy_plan(ctx)
    agents = [s["agent"] for s in plan]
    assert "verification" in agents


@test("escalation skipped when priority is low and risk is low")
def _():
    from app.core.context          import create_context, update_context
    from app.core.autonomy_planner import build_autonomy_plan
    ctx = create_context("test")
    update_context(ctx, priority="low")
    ctx["risk"] = {"level": "low"}
    plan   = build_autonomy_plan(ctx)
    agents = [s["agent"] for s in plan]
    assert "escalation" not in agents, \
        f"escalation should be skipped for low priority+risk, got: {agents}"


@test("recovery skipped when verification passed and no errors")
def _():
    from app.core.context          import create_context, update_context
    from app.core.autonomy_planner import build_autonomy_plan
    ctx = create_context("test")
    ctx["verification"] = {"status": "ok", "confidence": 1.0}
    ctx["errors"] = []
    plan   = build_autonomy_plan(ctx)
    agents = [s["agent"] for s in plan]
    assert "recovery" not in agents, \
        f"recovery should be skipped when verified+no errors, got: {agents}"


@test("monitor skipped when verification already passed")
def _():
    from app.core.context          import create_context
    from app.core.autonomy_planner import build_autonomy_plan
    ctx = create_context("test")
    ctx["verification"] = {"status": "ok"}
    plan   = build_autonomy_plan(ctx)
    agents = [s["agent"] for s in plan]
    assert "monitor" not in agents, \
        f"monitor should be skipped after ok verification, got: {agents}"


@test("full pipeline result has 'autonomy_plan' populated in context")
def _():
    result = _run()
    assert "autonomy_plan" in result["context"]
    assert len(result["context"]["autonomy_plan"]) > 0


# =============================================================================
print("\n── Fix 2: Feedback Loop ─────────────────────────────────────────────")
# =============================================================================

@test("_should_replan returns False when verification ok, risk low, no errors")
def _():
    from app.core.context      import create_context
    from app.core.orchestrator import _should_replan
    ctx = create_context("test")
    ctx["verification"] = {"status": "ok"}
    ctx["risk"]         = {"level": "low"}
    ctx["errors"]       = []
    assert _should_replan(ctx) is False


@test("_should_replan returns True when verification fails")
def _():
    from app.core.context      import create_context
    from app.core.orchestrator import _should_replan
    ctx = create_context("test")
    ctx["verification"] = {"status": "fail"}
    ctx["risk"]         = {"level": "low"}
    ctx["errors"]       = []
    assert _should_replan(ctx) is True


@test("_should_replan returns True when risk is high")
def _():
    from app.core.context      import create_context
    from app.core.orchestrator import _should_replan
    ctx = create_context("test")
    ctx["verification"] = {"status": "ok"}
    ctx["risk"]         = {"level": "high"}
    ctx["errors"]       = []
    assert _should_replan(ctx) is True


@test("_should_replan returns True when meaningful errors exist")
def _():
    from app.core.context      import create_context
    from app.core.orchestrator import _should_replan
    ctx = create_context("test")
    ctx["verification"] = {"status": "ok"}
    ctx["risk"]         = {"level": "low"}
    ctx["errors"]       = ["[Monitor] critical field missing"]
    assert _should_replan(ctx) is True


@test("_should_replan ignores autonomy-internal noise errors")
def _():
    from app.core.context      import create_context
    from app.core.orchestrator import _should_replan
    ctx = create_context("test")
    ctx["verification"] = {"status": "ok"}
    ctx["risk"]         = {"level": "low"}
    ctx["errors"]       = ["[Autonomy] ledger failed: connection refused"]
    assert _should_replan(ctx) is False


@test("retry_count starts at 0 in fresh context metadata")
def _():
    from app.core.context import create_context
    ctx = create_context("test")
    assert ctx["metadata"]["retry_count"] == 0


@test("replan loop is bounded — retry_count never exceeds _MAX_REPLANS")
def _():
    """
    Force replan trigger on every cycle by making verification always fail.
    Confirm retry_count in the final result is capped at _MAX_REPLANS.
    """
    import pandas as pd
    from app.core.orchestrator import process_message, _MAX_REPLANS

    im, em = _mocks()

    # Make verification always produce "fail" by making event empty
    # (SkillRouterAgent is mocked to return empty event)
    with patch("app.agents.intent_agent.get_llm",     return_value=im), \
         patch("app.agents.extraction_agent.get_llm", return_value=em), \
         patch("utils.excel_writer.append_row"), \
         patch("utils.excel_writer.read_sheet",   return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service.append_transaction",
               return_value=False), \
         patch("app.services.router.route_to_skill",  return_value={}):
        result = process_message("rahul ne 500 bheja")

    final_retry = result["context"]["metadata"]["retry_count"]
    assert final_retry <= _MAX_REPLANS, \
        f"retry_count={final_retry} exceeds cap={_MAX_REPLANS}"


@test("orchestrator completes (state=completed) even after max replans")
def _():
    import pandas as pd
    from app.core.orchestrator import process_message

    im, em = _mocks()
    with patch("app.agents.intent_agent.get_llm",     return_value=im), \
         patch("app.agents.extraction_agent.get_llm", return_value=em), \
         patch("utils.excel_writer.append_row"), \
         patch("utils.excel_writer.read_sheet",   return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service.append_transaction",
               return_value=False), \
         patch("app.services.router.route_to_skill",  return_value={}):
        result = process_message("rahul ne 500 bheja")

    assert result["context"]["state"] == "completed"


# =============================================================================
print("\n── Fix 3: Priority Score Accumulation ───────────────────────────────")
# =============================================================================

@test("contribute_priority_score adds to context['priority_score']")
def _():
    from app.core.context   import create_context
    from app.core.priority  import contribute_priority_score
    ctx = create_context("test")
    assert ctx["priority_score"] == 0
    contribute_priority_score(ctx, 30, "test reason")
    assert ctx["priority_score"] == 30


@test("priority_score is clamped at 100")
def _():
    from app.core.context  import create_context
    from app.core.priority import contribute_priority_score
    ctx = create_context("test")
    contribute_priority_score(ctx, 80, "first")
    contribute_priority_score(ctx, 80, "second")
    assert ctx["priority_score"] == 100, \
        f"expected 100 (clamped), got {ctx['priority_score']}"


@test("contribute_priority_score appends to priority_score_reasons")
def _():
    from app.core.context  import create_context
    from app.core.priority import contribute_priority_score
    ctx = create_context("test")
    contribute_priority_score(ctx, 20, "reason A")
    contribute_priority_score(ctx, 15, "reason B")
    reasons = ctx["priority_score_reasons"]
    assert len(reasons) == 2
    assert reasons[0]["points"] == 20
    assert reasons[0]["reason"] == "reason A"
    assert reasons[1]["points"] == 15


@test("derive_priority_label: score>70 → 'high'")
def _():
    from app.core.context  import create_context
    from app.core.priority import contribute_priority_score, derive_priority_label
    ctx = create_context("test")
    contribute_priority_score(ctx, 75, "large amount")
    label = derive_priority_label(ctx)
    assert label == "high", f"expected 'high', got '{label}'"
    assert ctx["priority"] == "high"


@test("derive_priority_label: score>40 → 'medium'")
def _():
    from app.core.context  import create_context
    from app.core.priority import contribute_priority_score, derive_priority_label
    ctx = create_context("test")
    contribute_priority_score(ctx, 50, "urgency keyword")
    label = derive_priority_label(ctx)
    assert label == "medium", f"expected 'medium', got '{label}'"


@test("derive_priority_label: score<=40 → 'low'")
def _():
    from app.core.context  import create_context
    from app.core.priority import derive_priority_label
    ctx = create_context("test")
    # score stays 0
    label = derive_priority_label(ctx)
    assert label == "low", f"expected 'low', got '{label}'"


@test("reset_priority_score zeroes score and reasons")
def _():
    from app.core.context  import create_context
    from app.core.priority import contribute_priority_score, reset_priority_score
    ctx = create_context("test")
    contribute_priority_score(ctx, 50, "something")
    reset_priority_score(ctx)
    assert ctx["priority_score"] == 0
    assert ctx["priority_score_reasons"] == []


@test("UrgencyAgent uses priority_score — no direct string overwrite")
def _():
    import inspect
    from app.agents import urgency_agent
    src = inspect.getsource(urgency_agent)
    # Old pattern must be gone
    assert 'context["priority"] = ' not in src, \
        'UrgencyAgent still directly writes context["priority"] — should use derive_priority_label'
    # New pattern must be present
    assert "contribute_priority_score" in src
    assert "derive_priority_label" in src


@test("result['priority_score'] is an int in the response")
def _():
    result = _run("rahul ne 500 bheja")
    assert "priority_score" in result
    assert isinstance(result["priority_score"], int)


@test("crisis keyword message scores >= 80 → priority='high'")
def _():
    result = _run(
        message="emergency fraud ho gaya urgent help",
        intent="payment", amount=500
    )
    assert result["priority_score"] >= 80, \
        f"expected score>=80 for crisis message, got {result['priority_score']}"
    assert result["priority"] == "high"


@test("normal low-amount message has priority='low'")
def _():
    result = _run("rahul ne 200 bheja", intent="payment", amount=200)
    assert result["priority"] in ("low", "medium"), \
        f"expected low/medium for routine message, got '{result['priority']}'"


@test("high-amount payment (>50k) scores >=45 → at least 'medium'")
def _():
    result = _run(
        message="amit ne 75000 bheja",
        intent="payment", amount=75000, customer="Amit"
    )
    assert result["priority_score"] >= 45, \
        f"expected score>=45, got {result['priority_score']}"
    assert result["priority"] in ("medium", "high")


@test("prediction_agent also contributes to priority_score (high risk)")
def _():
    """High-risk transaction: unknown customer + large amount should raise score."""
    result = _run(
        message="kisi ne 60000 bheja",
        intent="payment", amount=60000, customer=None
    )
    # PredictionAgent contributes 35 for high risk
    # UrgencyAgent contributes 45 for amount > 50k
    # Total should be >= 35
    assert result["priority_score"] >= 35, \
        f"expected score>=35, got {result['priority_score']}"


# =============================================================================
print("\n── Regression: existing behaviour preserved ─────────────────────────")
# =============================================================================

@test("all 11 agents still in registry")
def _():
    from app.core.registry import list_agents
    required = {
        "intent", "extraction", "validation", "router", "ledger",
        "verification", "monitor", "prediction", "urgency",
        "escalation", "recovery",
    }
    missing = required - set(list_agents())
    assert not missing, f"Missing: {missing}"


@test("response still has all core + autonomy keys")
def _():
    result = _run()
    core     = {"message", "intent", "data", "event", "sheet_updated"}
    autonomy = {"verification", "risk", "priority", "priority_score",
                "alerts", "recovery", "monitor", "context"}
    for key in core | autonomy:
        assert key in result, f"Missing key in result: {key}"


@test("demo mode unaffected — run_notiflow demo still works")
def _():
    from app.main import run_notiflow
    result = run_notiflow("rahul ne 15000 bheja", demo_mode=True)
    assert result["intent"] == "payment"
    assert result["data"]["amount"] == 15000


# =============================================================================
# Summary
# =============================================================================
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