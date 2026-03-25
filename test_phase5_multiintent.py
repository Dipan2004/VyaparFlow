"""
test_phase5_multiintent.py
--------------------------
Phase 5 Tests: Multi-Intent Understanding and Execution

Covers:
    1. IntentAgent._parse — new intents[] format  
    2. IntentAgent._parse — backward compat with old {intent:} format
    3. Context schema — intents + multi_data fields present
    4. ExtractionAgent — multi-intent extraction keyed by intent
    5. ExtractionAgent — single-intent path unchanged
    6. Planner — extraction skip logic respects multi_data
    7. Full pipeline — payment+order+urgency detected and extracted
    8. Full pipeline — single-intent message unchanged (regression)
    9. Result shape — intents + multi_data in response

Run:  python test_phase5_multiintent.py
No API keys required — LLM calls are mocked.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

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


def _make_mocks(intents: list[str], intent_raw: str, extract_raw: str):
    im = MagicMock()
    em = MagicMock()
    im.generate.return_value = intent_raw
    em.generate.return_value = extract_raw
    return im, em


def _run(message: str, intent_raw: str, extract_raw: str):
    from app.core.orchestrator import process_message
    im, em = _make_mocks([], intent_raw, extract_raw)
    with patch("app.agents.intent_agent.get_llm",     return_value=im), \
         patch("app.agents.extraction_agent.get_llm", return_value=em), \
         patch("utils.excel_writer.append_row"), \
         patch("utils.excel_writer.read_sheet",       return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service.append_transaction", return_value=False):
        return process_message(message)


# =============================================================================
print("\n── 1. IntentAgent._parse — new intents[] format ─────────────────────")
# =============================================================================

@test("_parse returns list for multi-intent JSON response")
def _():
    from app.agents.intent_agent import IntentAgent
    result = IntentAgent._parse('{"intents": ["payment", "order"]}')
    assert result == ["payment", "order"], f"got {result}"


@test("_parse returns single-element list for single-intent JSON response")
def _():
    from app.agents.intent_agent import IntentAgent
    result = IntentAgent._parse('{"intents": ["payment"]}')
    assert result == ["payment"], f"got {result}"


@test("_parse backward compat — old {intent: x} format wrapped in list")
def _():
    from app.agents.intent_agent import IntentAgent
    result = IntentAgent._parse('{"intent": "payment"}')
    assert result == ["payment"], f"got {result}"


@test("_parse filters out unknown intents, keeps valid ones")
def _():
    from app.agents.intent_agent import IntentAgent
    result = IntentAgent._parse('{"intents": ["payment", "unicorn", "order"]}')
    assert "unicorn" not in result
    assert "payment" in result
    assert "order" in result


@test("_parse returns ['other'] on garbage input")
def _():
    from app.agents.intent_agent import IntentAgent
    result = IntentAgent._parse("this is not json at all")
    assert result == ["other"], f"got {result}"


@test("_parse deduplicates repeated intents")
def _():
    from app.agents.intent_agent import IntentAgent
    result = IntentAgent._parse('{"intents": ["payment", "payment", "order"]}')
    assert result.count("payment") == 1, f"duplicate found: {result}"


@test("_parse works with regex fallback for intents array")
def _():
    from app.agents.intent_agent import IntentAgent
    # Malformed JSON but regex can still find the intents array
    result = IntentAgent._parse('{"intents": ["order", "payment"')
    assert "order" in result


# =============================================================================
print("\n── 2. Context schema ────────────────────────────────────────────────")
# =============================================================================

@test("create_context has 'intents' key initialized to []")
def _():
    from app.core.context import create_context
    ctx = create_context("test")
    assert "intents" in ctx
    assert ctx["intents"] == []


@test("create_context has 'multi_data' key initialized to {}")
def _():
    from app.core.context import create_context
    ctx = create_context("test")
    assert "multi_data" in ctx
    assert ctx["multi_data"] == {}


@test("IntentAgent sets context['intents'] as a list")
def _():
    from app.agents.intent_agent import IntentAgent
    from app.core.context import create_context

    agent   = IntentAgent()
    ctx     = create_context("test")
    mock    = MagicMock()
    mock.generate.return_value = '{"intents": ["payment", "order"]}'

    with patch("app.agents.intent_agent.get_llm", return_value=mock):
        agent.execute(ctx)

    assert ctx["intents"] == ["payment", "order"]
    assert ctx["intent"]  == "payment"  # backward compat


@test("IntentAgent backward compat — context['intent'] = intents[0]")
def _():
    from app.agents.intent_agent import IntentAgent
    from app.core.context import create_context

    agent = IntentAgent()
    ctx   = create_context("test")
    mock  = MagicMock()
    mock.generate.return_value = '{"intents": ["credit", "order"]}'

    with patch("app.agents.intent_agent.get_llm", return_value=mock):
        agent.execute(ctx)

    assert ctx["intent"] == "credit"


# =============================================================================
print("\n── 3. ExtractionAgent — multi-intent ───────────────────────────────")
# =============================================================================

@test("ExtractionAgent sets multi_data keyed by intent")
def _():
    from app.agents.extraction_agent import ExtractionAgent
    from app.core.context import create_context, update_context

    agent = ExtractionAgent()
    ctx   = create_context("rahul ne 5000 bheja aur 5 kurti bhej dena")
    update_context(ctx, intent="payment", intents=["payment", "order"])

    mock = MagicMock()
    mock.generate.return_value = json.dumps({
        "payment": {"customer": "Rahul", "amount": 5000, "payment_type": None},
        "order":   {"customer": None, "item": "kurti", "quantity": 5},
    })

    with patch("app.agents.extraction_agent.get_llm", return_value=mock):
        agent.execute(ctx)

    assert "payment" in ctx["multi_data"]
    assert "order"   in ctx["multi_data"]
    assert ctx["multi_data"]["payment"]["amount"]   == 5000
    assert ctx["multi_data"]["order"]["quantity"]   == 5


@test("ExtractionAgent context['data'] = primary intent data (backward compat)")
def _():
    from app.agents.extraction_agent import ExtractionAgent
    from app.core.context import create_context, update_context

    agent = ExtractionAgent()
    ctx   = create_context("test")
    update_context(ctx, intent="payment", intents=["payment", "order"])

    mock = MagicMock()
    mock.generate.return_value = json.dumps({
        "payment": {"customer": "Rahul", "amount": 500, "payment_type": None},
        "order":   {"customer": None, "item": "kurti", "quantity": 3},
    })

    with patch("app.agents.extraction_agent.get_llm", return_value=mock):
        agent.execute(ctx)

    # data must equal the primary intent's data
    assert ctx["data"] == ctx["multi_data"]["payment"]
    assert ctx["data"]["amount"] == 500


@test("ExtractionAgent single-intent — flat JSON response still works")
def _():
    from app.agents.extraction_agent import ExtractionAgent
    from app.core.context import create_context, update_context

    agent = ExtractionAgent()
    ctx   = create_context("rahul ne 500 bheja")
    update_context(ctx, intent="payment", intents=["payment"])

    mock = MagicMock()
    mock.generate.return_value = json.dumps(
        {"customer": "Rahul", "amount": 500, "payment_type": None}
    )

    with patch("app.agents.extraction_agent.get_llm", return_value=mock):
        agent.execute(ctx)

    assert ctx["data"]["amount"] == 500
    assert ctx["multi_data"]["payment"]["amount"] == 500


@test("ExtractionAgent fills missing intents with null-data")
def _():
    from app.agents.extraction_agent import ExtractionAgent
    from app.core.context import create_context, update_context

    agent = ExtractionAgent()
    ctx   = create_context("test")
    update_context(ctx, intent="payment", intents=["payment", "order"])

    mock = MagicMock()
    # LLM only returns payment, misses order
    mock.generate.return_value = json.dumps(
        {"payment": {"customer": "X", "amount": 100, "payment_type": None}}
    )

    with patch("app.agents.extraction_agent.get_llm", return_value=mock):
        agent.execute(ctx)

    assert "order" in ctx["multi_data"]
    # order fields should all be None
    assert all(v is None for v in ctx["multi_data"]["order"].values())


# =============================================================================
print("\n── 4. UrgencyAgent — Hinglish urgency keywords ──────────────────────")
# =============================================================================

@test("'jaldi' is in UrgencyAgent._URGENT_KEYWORDS")
def _():
    from app.agents.urgency_agent import _URGENT_KEYWORDS
    assert "jaldi" in _URGENT_KEYWORDS


@test("'urgent' is in UrgencyAgent._URGENT_KEYWORDS")
def _():
    from app.agents.urgency_agent import _URGENT_KEYWORDS
    assert "urgent" in _URGENT_KEYWORDS


@test("'asap' is in UrgencyAgent._URGENT_KEYWORDS")
def _():
    from app.agents.urgency_agent import _URGENT_KEYWORDS
    assert "asap" in _URGENT_KEYWORDS


@test("UrgencyAgent adds 50 points for 'jaldi' in message")
def _():
    from app.agents.urgency_agent import UrgencyAgent
    from app.core.context import create_context, update_context

    agent = UrgencyAgent()
    ctx   = create_context("5 kurti bhej dena jaldi")
    update_context(ctx, intent="order", risk={})

    agent.execute(ctx)
    assert ctx["priority_score"] >= 50, \
        f"expected >=50 for 'jaldi', got {ctx['priority_score']}"


# =============================================================================
print("\n── 5. Full pipeline — payment + order + urgency ─────────────────────")
# =============================================================================

@test("full pipeline detects payment+order intents")
def _():
    result = _run(
        message     = "rahul ne 5000 bheja aur 5 kurti bhej dena jaldi",
        intent_raw  = '{"intents": ["payment", "order"]}',
        extract_raw = json.dumps({
            "payment": {"customer": "Rahul", "amount": 5000, "payment_type": None},
            "order":   {"customer": None, "item": "kurti", "quantity": 5},
        }),
    )
    assert "payment" in result["intents"], f"intents={result['intents']}"
    assert "order"   in result["intents"], f"intents={result['intents']}"


@test("full pipeline result has 'intents' as a list")
def _():
    result = _run(
        message     = "rahul ne 5000 bheja",
        intent_raw  = '{"intents": ["payment"]}',
        extract_raw = json.dumps({"customer": "Rahul", "amount": 5000, "payment_type": None}),
    )
    assert isinstance(result["intents"], list)
    assert len(result["intents"]) >= 1


@test("full pipeline result has 'multi_data' with per-intent extractions")
def _():
    result = _run(
        message     = "rahul ne 5000 bheja aur 5 kurti bhej dena",
        intent_raw  = '{"intents": ["payment", "order"]}',
        extract_raw = json.dumps({
            "payment": {"customer": "Rahul", "amount": 5000, "payment_type": None},
            "order":   {"customer": None, "item": "kurti", "quantity": 5},
        }),
    )
    md = result["multi_data"]
    assert "payment" in md
    assert "order"   in md
    assert md["payment"]["amount"]   == 5000
    assert md["order"]["quantity"]   == 5


@test("full pipeline result['intent'] = primary (backward compat)")
def _():
    result = _run(
        message     = "rahul ne 5000 bheja aur 5 kurti bhej dena",
        intent_raw  = '{"intents": ["payment", "order"]}',
        extract_raw = json.dumps({
            "payment": {"customer": "Rahul", "amount": 5000, "payment_type": None},
            "order":   {"customer": None, "item": "kurti", "quantity": 5},
        }),
    )
    assert result["intent"] == "payment"   # first in list


@test("full pipeline result['data'] = primary intent data (backward compat)")
def _():
    result = _run(
        message     = "rahul ne 5000 bheja aur 5 kurti bhej dena",
        intent_raw  = '{"intents": ["payment", "order"]}',
        extract_raw = json.dumps({
            "payment": {"customer": "Rahul", "amount": 5000, "payment_type": None},
            "order":   {"customer": None, "item": "kurti", "quantity": 5},
        }),
    )
    assert result["data"]["amount"] == 5000   # payment data


# =============================================================================
print("\n── 6. Single-intent regression ──────────────────────────────────────")
# =============================================================================

@test("single-intent message still works unchanged")
def _():
    result = _run(
        message     = "rahul ne 500 bheja",
        intent_raw  = '{"intents": ["payment"]}',
        extract_raw = json.dumps({"customer": "Rahul", "amount": 500, "payment_type": None}),
    )
    assert result["intent"]          == "payment"
    assert result["data"]["amount"]  == 500
    assert result["intents"]         == ["payment"]


@test("old-format LLM response {intent: x} still produces correct result")
def _():
    result = _run(
        message     = "rahul ne 500 bheja",
        intent_raw  = '{"intent": "payment"}',   # old format
        extract_raw = json.dumps({"customer": "Rahul", "amount": 500, "payment_type": None}),
    )
    assert result["intent"]          == "payment"
    assert result["data"]["amount"]  == 500


@test("demo mode run_notiflow still works (regression)")
def _():
    from app.main import run_notiflow
    result = run_notiflow("rahul ne 15000 bheja", demo_mode=True)
    assert result["intent"]          == "payment"
    assert result["data"]["amount"]  == 15000


@test("all 11 agents still registered (regression)")
def _():
    from app.core.registry import list_agents
    required = {
        "intent", "extraction", "validation", "router", "ledger",
        "verification", "monitor", "prediction", "urgency",
        "escalation", "recovery",
    }
    missing = required - set(list_agents())
    assert not missing, f"Missing: {missing}"


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
