"""
test_pipeline.py
----------------
Smoke tests for NotiFlow Autonomous v2 pipeline.

Runs without any API keys (uses demo mode + mocks for LLM).
Run with:  python test_pipeline.py

Tests:
  1. Context creation and shape
  2. BaseAgent error isolation
  3. Demo pipeline end-to-end (all 8 canned messages)
  4. LLM mock: intent agent in isolation
  5. LLM mock: extraction agent in isolation
  6. Full live pipeline mock (all 5 agents in sequence)
  7. Backward-compat: legacy functional APIs
"""

from __future__ import annotations

import sys
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is on path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("NOTIFLOW_DEMO_MODE", "true")

PASS = "✅"
FAIL = "❌"
_results: list[tuple[str, bool, str]] = []


def test(name: str):
    """Decorator that records pass/fail."""
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
print("\n── 1. Context shape ─────────────────────────────────────────────────")

@test("create_context returns correct keys")
def _():
    from app.core.context import create_context
    ctx = create_context("test message", source="whatsapp")
    required = {"message", "intent", "data", "event", "state",
                "history", "errors", "priority", "plan", "metadata"}
    assert required == set(ctx.keys()), f"Missing keys: {required - set(ctx.keys())}"
    assert ctx["message"] == "test message"
    assert ctx["state"] == "initialized"
    assert ctx["metadata"]["source"] == "whatsapp"


@test("update_context mutates in-place and returns same object")
def _():
    from app.core.context import create_context, update_context
    ctx = create_context("x")
    result = update_context(ctx, intent="order", state="intent_detected")
    assert result is ctx
    assert ctx["intent"] == "order"
    assert ctx["state"] == "intent_detected"


@test("update_context supports double-underscore nested keys")
def _():
    from app.core.context import create_context, update_context
    ctx = create_context("x")
    update_context(ctx, metadata__source="gpay")
    assert ctx["metadata"]["source"] == "gpay"


@test("log_step appends to history")
def _():
    from app.core.context import create_context, log_step
    ctx = create_context("x")
    log_step(ctx, "TestAgent", "success", "all good")
    assert len(ctx["history"]) == 1
    assert ctx["history"][0]["agent"] == "TestAgent"
    assert ctx["history"][0]["status"] == "success"


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 2. BaseAgent error isolation ─────────────────────────────────────")

@test("BaseAgent.run captures exception, sets state=failed, re-raises")
def _():
    from app.core.base_agent import BaseAgent
    from app.core.context import create_context

    class BrokenAgent(BaseAgent):
        name = "BrokenAgent"
        def execute(self, ctx):
            raise ValueError("intentional failure")

    ctx = create_context("x")
    try:
        BrokenAgent().run(ctx)
        assert False, "Should have raised"
    except ValueError:
        pass
    assert ctx["state"] == "failed"
    assert len(ctx["errors"]) == 1
    assert "BrokenAgent" in ctx["errors"][0]
    assert len(ctx["history"]) == 1
    assert ctx["history"][0]["status"] == "error"


@test("BaseAgent.run logs success to history on clean execute")
def _():
    from app.core.base_agent import BaseAgent
    from app.core.context import create_context

    class GoodAgent(BaseAgent):
        name = "GoodAgent"
        def execute(self, ctx):
            ctx["data"]["ok"] = True
            return ctx

    ctx = create_context("x")
    GoodAgent().run(ctx)
    assert ctx["data"]["ok"] is True
    assert ctx["history"][0]["status"] == "success"


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 3. Demo pipeline end-to-end ──────────────────────────────────────")

DEMO_CASES = [
    ("rahul ne 15000 bheja",               "payment"),
    ("bhaiya 3 kurti bhej dena",           "order"),
    ("priya ke liye 2 kilo aata bhej dena","order"),
    ("size chota hai exchange karna hai",  "return"),
    ("udhar me de dijiye",                 "credit"),
    ("suresh ko 500 ka maal udhar dena",   "credit"),
    ("3 kurti ka set ready rakhna",        "preparation"),
    ("amit bhai ka 8000 gpay se aaya",     "payment"),
]

for msg, expected_intent in DEMO_CASES:
    @test(f"demo: '{msg[:35]}...' → {expected_intent}")
    def _(m=msg, ei=expected_intent):
        from app.main import run_notiflow
        result = run_notiflow(m, demo_mode=True)
        assert "intent" in result
        assert "data" in result
        assert "event" in result
        assert result["intent"] == ei, f"got {result['intent']!r}, want {ei!r}"


@test("demo: unknown message uses keyword fallback")
def _():
    from app.main import run_notiflow
    result = run_notiflow("kuch aur bheja tha gpay se", demo_mode=True)
    assert result["intent"] in {"payment", "order", "credit", "return", "preparation", "other"}


@test("run_notiflow raises ValueError on empty message")
def _():
    from app.main import run_notiflow
    try:
        run_notiflow("   ", demo_mode=True)
        assert False, "Should have raised"
    except ValueError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 4. IntentAgent (LLM mocked) ──────────────────────────────────────")

@test("IntentAgent writes intent to context")
def _():
    from app.core.context import create_context
    from app.agents.intent_agent import IntentAgent

    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"intent": "payment"}'

    with patch("app.agents.intent_agent.get_llm", return_value=mock_llm):
        ctx = create_context("rahul ne paisa bheja")
        ctx = IntentAgent().run(ctx)

    assert ctx["intent"] == "payment"
    assert ctx["state"] == "intent_detected"


@test("IntentAgent defaults to 'other' on bad JSON response")
def _():
    from app.core.context import create_context
    from app.agents.intent_agent import IntentAgent

    mock_llm = MagicMock()
    mock_llm.generate.return_value = "sorry, I cannot answer that"

    with patch("app.agents.intent_agent.get_llm", return_value=mock_llm):
        ctx = create_context("random text")
        ctx = IntentAgent().run(ctx)

    assert ctx["intent"] == "other"


@test("IntentAgent rejects unknown intent, defaults to 'other'")
def _():
    from app.core.context import create_context
    from app.agents.intent_agent import IntentAgent

    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"intent": "dancing"}'

    with patch("app.agents.intent_agent.get_llm", return_value=mock_llm):
        ctx = create_context("random")
        ctx = IntentAgent().run(ctx)

    assert ctx["intent"] == "other"


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 5. ExtractionAgent (LLM mocked) ──────────────────────────────────")

@test("ExtractionAgent extracts payment fields")
def _():
    from app.core.context import create_context, update_context
    from app.agents.extraction_agent import ExtractionAgent

    mock_llm = MagicMock()
    mock_llm.generate.return_value = json.dumps({
        "customer": "Rahul", "amount": 15000, "payment_type": None
    })

    with patch("app.agents.extraction_agent.get_llm", return_value=mock_llm):
        ctx = create_context("rahul ne 15000 bheja")
        update_context(ctx, intent="payment")
        ctx = ExtractionAgent().run(ctx)

    assert ctx["data"]["customer"] == "Rahul"
    assert ctx["data"]["amount"] == 15000
    assert ctx["state"] == "extracted"


@test("ExtractionAgent normalises customer to Title Case")
def _():
    from app.core.context import create_context, update_context
    from app.agents.extraction_agent import ExtractionAgent

    mock_llm = MagicMock()
    mock_llm.generate.return_value = json.dumps({
        "customer": "rahul kumar", "amount": 500, "payment_type": "cash"
    })

    with patch("app.agents.extraction_agent.get_llm", return_value=mock_llm):
        ctx = create_context("rahul ne bheja")
        update_context(ctx, intent="payment")
        ctx = ExtractionAgent().run(ctx)

    assert ctx["data"]["customer"] == "Rahul Kumar"


@test("ExtractionAgent handles unparseable JSON gracefully")
def _():
    from app.core.context import create_context, update_context
    from app.agents.extraction_agent import ExtractionAgent

    mock_llm = MagicMock()
    mock_llm.generate.return_value = "not json at all"

    with patch("app.agents.extraction_agent.get_llm", return_value=mock_llm):
        ctx = create_context("garbled text")
        update_context(ctx, intent="order")
        ctx = ExtractionAgent().run(ctx)

    # Should return null-filled schema, not crash
    assert "item" in ctx["data"]
    assert ctx["state"] == "extracted"


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 6. Full live pipeline mock ────────────────────────────────────────")

@test("Full pipeline: payment message → payment_recorded event")
def _():
    from app.core.orchestrator import process_message

    mock_llm = MagicMock()
    # Intent call
    mock_llm.generate.side_effect = [
        '{"intent": "payment"}',
        json.dumps({"customer": "Amit", "amount": 8000, "payment_type": "upi"}),
    ]

    with patch("app.agents.intent_agent.get_llm", return_value=mock_llm), \
         patch("app.agents.extraction_agent.get_llm", return_value=mock_llm), \
         patch("app.utils.excel_writer.append_row"), \
         patch("app.utils.excel_writer.read_sheet", return_value=__import__("pandas").DataFrame()), \
         patch("app.services.google_sheets_service._get_sheet", return_value=None):

        result = process_message("amit bhai ka 8000 gpay se aaya", source="whatsapp")

    assert result["intent"] == "payment"
    assert result["data"]["customer"] == "Amit"
    assert result["data"]["amount"] == 8000
    assert result["data"]["payment_type"] == "upi"
    assert result["event"]["event"] == "payment_recorded"
    assert "context" in result        # new v2 field
    assert result["context"]["state"] == "completed"


@test("Full pipeline: order message → order_received event")
def _():
    from app.core.orchestrator import process_message

    intent_llm  = MagicMock()
    extract_llm = MagicMock()
    intent_llm.generate.return_value  = '{"intent": "order"}'
    extract_llm.generate.return_value = json.dumps(
        {"customer": "Priya", "item": "kurti", "quantity": 3}
    )

    import pandas as pd
    with patch("app.agents.intent_agent.get_llm",     return_value=intent_llm), \
         patch("app.agents.extraction_agent.get_llm", return_value=extract_llm), \
         patch("app.utils.excel_writer.append_row"), \
         patch("app.utils.excel_writer.read_sheet",   return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service._get_sheet", return_value=None):

        result = process_message("priya ke liye 3 kurti bhej dena")

    assert result["intent"] == "order"
    assert result["event"]["event"] == "order_received"
    assert result["event"]["order"]["item"] == "kurti"
    assert result["event"]["order"]["quantity"] == 3


@test("Full pipeline: LedgerAgent failure does not crash pipeline")
def _():
    from app.core.orchestrator import process_message

    mock_llm = MagicMock()
    mock_llm.generate.side_effect = [
        '{"intent": "payment"}',
        json.dumps({"customer": "Test", "amount": 100, "payment_type": None}),
    ]

    import pandas as pd
    with patch("app.agents.intent_agent.get_llm",     return_value=mock_llm), \
         patch("app.agents.extraction_agent.get_llm", return_value=mock_llm), \
         patch("app.utils.excel_writer.append_row"), \
         patch("app.utils.excel_writer.read_sheet",   return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service._get_sheet",
               side_effect=Exception("Sheets exploded")):

        result = process_message("test 100 bheja")

    # Pipeline must complete even if Sheets fails
    assert result["intent"] == "payment"
    assert result["sheet_updated"] is False
    assert result["context"]["state"] == "completed"


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 7. Backward-compat: legacy functional APIs ────────────────────────")

@test("agent.intent_agent.detect_intent() still works")
def _():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"intent": "credit"}'
    with patch("app.agents.intent_agent.get_llm", return_value=mock_llm):
        from agent.intent_agent import detect_intent
        result = detect_intent("udhar chahiye")
    assert result == {"intent": "credit"}


@test("agent.extraction_agent.extract_fields() still works")
def _():
    mock_llm = MagicMock()
    mock_llm.generate.return_value = json.dumps(
        {"customer": "Suresh", "item": "goods", "quantity": None, "amount": 500}
    )
    with patch("app.agents.extraction_agent.get_llm", return_value=mock_llm):
        from agent.extraction_agent import extract_fields
        result = extract_fields("suresh ko 500 udhar dena", "credit")
    assert result["intent"] == "credit"
    assert result["customer"] == "Suresh"
    assert result["amount"] == 500


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 8. LLMService (unit) ──────────────────────────────────────────────")

@test("LLMService falls back to Gemini when NIM raises")
def _():
    from app.core.llm_service import LLMService

    svc = LLMService()
    with patch.object(svc, "_call_nim", side_effect=RuntimeError("NIM down")), \
         patch.object(svc, "_call_gemini", return_value='{"intent":"order"}') as mock_gem:
        result = svc.generate("test prompt")
    assert result == '{"intent":"order"}'
    mock_gem.assert_called_once()


@test("LLMService raises RuntimeError when both backends fail")
def _():
    from app.core.llm_service import LLMService

    svc = LLMService()
    with patch.object(svc, "_call_nim",    side_effect=RuntimeError("NIM down")), \
         patch.object(svc, "_call_gemini", side_effect=RuntimeError("Gemini down")):
        try:
            svc.generate("test prompt")
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "NIM" in str(e) or "backends" in str(e).lower()


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
total   = len(_results)
passed  = sum(1 for _, ok, _ in _results if ok)
failed  = total - passed

print(f"\n{'─'*60}")
print(f"  Results: {passed}/{total} passed", end="")
if failed:
    print(f"  ({failed} failed)")
    print("\n  Failed tests:")
    for name, ok, err in _results:
        if not ok:
            print(f"    {FAIL}  {name}")
            print(f"         {err}")
else:
    print("  — all green ✅")
print(f"{'─'*60}\n")

sys.exit(0 if failed == 0 else 1)
