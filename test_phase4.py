"""
test_phase4.py
--------------
Phase 4 Tests: LLM Intelligence Layer

Covers:
    1. LLM Router — routing table, fallback order, default route
    2. LLMService — model iteration, context audit writes, provider dispatch
    3. Agent integration — intent + extraction pass agent_name/task_type
    4. Fallback logging — model_used / fallback_used in context and result
    5. Full pipeline — model selection visible end-to-end
    6. Failure resilience — partial failures, all-fail RuntimeError
    7. Backward compat — old generate(prompt) call still works

Run:  python test_phase4.py
No API keys required.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

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
print("\n── 1. LLM Router — routing table ────────────────────────────────────")
# ─────────────────────────────────────────────────────────────────────────────

@test("route_llm returns dict with 'primary' and 'fallbacks' keys")
def _():
    from app.core.llm_router import route_llm
    result = route_llm("IntentAgent", "classification")
    assert "primary"   in result, "missing 'primary'"
    assert "fallbacks" in result, "missing 'fallbacks'"


@test("primary ModelEntry has required keys: provider, model, max_tokens")
def _():
    from app.core.llm_router import route_llm
    result  = route_llm("IntentAgent", "classification")
    primary = result["primary"]
    for key in ("provider", "model", "max_tokens"):
        assert key in primary, f"ModelEntry missing key: {key}"


@test("IntentAgent/classification routes to NIM primary")
def _():
    from app.core.llm_router import route_llm
    result = route_llm("IntentAgent", "classification")
    assert result["primary"]["provider"] == "nim"


@test("ExtractionAgent/extraction routes to NIM primary")
def _():
    from app.core.llm_router import route_llm
    result = route_llm("ExtractionAgent", "extraction")
    assert result["primary"]["provider"] == "nim"


@test("planner/planning routes NIM primary, OpenRouter as fallback #1")
def _():
    from app.core.llm_router import route_llm
    result    = route_llm("planner", "planning")
    fallbacks = result["fallbacks"]
    assert result["primary"]["provider"] == "nim"
    assert fallbacks[0]["provider"] == "openrouter", \
        f"Expected openrouter as fallback #1 for planner, got {fallbacks[0]['provider']}"


@test("reasoning agents (prediction, recovery) route OpenRouter before NIM-fallback")
def _():
    from app.core.llm_router import route_llm
    for agent in ("PredictionAgent", "RecoveryAgent"):
        result    = route_llm(agent, "reasoning")
        fallbacks = result["fallbacks"]
        assert fallbacks[0]["provider"] == "openrouter", \
            f"{agent}: expected openrouter as first fallback, got {fallbacks[0]['provider']}"


@test("unknown agent returns default route (3 models)")
def _():
    from app.core.llm_router import route_llm
    result     = route_llm("SomeUnknownAgent", "some_task")
    all_models = [result["primary"]] + result["fallbacks"]
    assert len(all_models) == 3, f"expected 3 models in default route, got {len(all_models)}"


@test("route_llm is case-insensitive for agent_name")
def _():
    from app.core.llm_router import route_llm
    lower = route_llm("intentagent", "classification")
    upper = route_llm("INTENTAGENT", "CLASSIFICATION")
    title = route_llm("IntentAgent", "Classification")
    assert lower["primary"]["model"] == upper["primary"]["model"] == title["primary"]["model"]


@test("route_llm() with no args returns default route")
def _():
    from app.core.llm_router import route_llm
    result     = route_llm()
    all_models = [result["primary"]] + result["fallbacks"]
    assert len(all_models) >= 2
    assert result["primary"]["provider"] in ("nim", "openrouter")


@test("fallbacks list has at least 2 entries for known agents")
def _():
    from app.core.llm_router import route_llm
    for agent, task in [
        ("IntentAgent",    "classification"),
        ("ExtractionAgent","extraction"),
        ("planner",        "planning"),
    ]:
        result = route_llm(agent, task)
        assert len(result["fallbacks"]) >= 2, \
            f"{agent}/{task}: expected >=2 fallbacks, got {len(result['fallbacks'])}"


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 2. LLMService — model iteration and routing ──────────────────────")
# ─────────────────────────────────────────────────────────────────────────────

@test("generate() calls _call_model with primary model first")
def _():
    from app.core.llm_service import LLMService
    svc = LLMService()
    calls = []

    def mock_call(provider, model, prompt, tokens):
        calls.append((provider, model))
        return "ok"

    svc._call_model = mock_call
    svc.generate("test", agent_name="IntentAgent", task_type="classification")
    # Primary must be the first call
    assert len(calls) == 1, f"Expected 1 call (primary succeeded), got {len(calls)}"
    assert calls[0][0] == "nim"


@test("generate() falls back to second model when primary fails")
def _():
    from app.core.llm_service import LLMService
    svc   = LLMService()
    calls = []

    def mock_call(provider, model, prompt, tokens):
        calls.append((provider, model))
        if len(calls) == 1:
            raise RuntimeError("primary down")
        return "fallback_response"

    svc._call_model = mock_call
    result = svc.generate("test", agent_name="IntentAgent", task_type="classification")
    assert result == "fallback_response"
    assert len(calls) == 2, f"Expected 2 calls (primary fail + fallback), got {len(calls)}"


@test("generate() raises RuntimeError only after all models exhausted")
def _():
    from app.core.llm_service import LLMService
    svc = LLMService()
    svc._call_model = lambda *a: (_ for _ in ()).throw(RuntimeError("all down"))

    try:
        svc.generate("test", agent_name="IntentAgent", task_type="classification")
        assert False, "Should have raised"
    except RuntimeError as e:
        assert "All LLM backends failed" in str(e)
        assert "Tried:" in str(e)


@test("generate() tries all 3 models before raising")
def _():
    from app.core.llm_service import LLMService
    svc   = LLMService()
    tried = []

    def mock_call(provider, model, prompt, tokens):
        tried.append(model)
        raise RuntimeError("down")

    svc._call_model = mock_call
    try:
        svc.generate("test", agent_name="IntentAgent", task_type="classification")
    except RuntimeError:
        pass
    assert len(tried) == 3, f"Expected 3 models tried, got {len(tried)}: {tried}"


@test("generate() with no agent_name/task_type still works (backward compat)")
def _():
    from app.core.llm_service import LLMService
    svc = LLMService()
    svc._call_model = lambda provider, model, prompt, tokens: "compat_response"
    result = svc.generate("test prompt")
    assert result == "compat_response"


@test("generate() positional max_tokens arg still accepted (backward compat)")
def _():
    from app.core.llm_service import LLMService
    svc = LLMService()

    captured_tokens = []
    def mock_call(provider, model, prompt, tokens):
        captured_tokens.append(tokens)
        return "ok"

    svc._call_model = mock_call
    svc.generate("test", 128)   # positional max_tokens
    assert captured_tokens[0] == 128, \
        f"expected max_tokens=128, got {captured_tokens[0]}"


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 3. Context audit writes — model_used / fallback_used ─────────────")
# ─────────────────────────────────────────────────────────────────────────────

@test("generate() writes model_used to context on success")
def _():
    from app.core.llm_service import LLMService
    from app.core.context     import create_context
    svc = LLMService()
    ctx = create_context("test")

    svc._call_model = lambda provider, model, prompt, tokens: "ok"
    svc.generate("test", context=ctx)

    assert "model_used" in ctx, "context missing 'model_used'"
    assert isinstance(ctx["model_used"], str)
    assert len(ctx["model_used"]) > 0


@test("generate() writes fallback_used=False when primary succeeds")
def _():
    from app.core.llm_service import LLMService
    from app.core.context     import create_context
    svc = LLMService()
    ctx = create_context("test")

    svc._call_model = lambda provider, model, prompt, tokens: "ok"
    svc.generate("test", context=ctx, agent_name="IntentAgent", task_type="classification")

    assert ctx.get("fallback_used") is False


@test("generate() writes fallback_used=True when fallback model used")
def _():
    from app.core.llm_service import LLMService
    from app.core.context     import create_context
    svc   = LLMService()
    ctx   = create_context("test")
    calls = [0]

    def mock_call(provider, model, prompt, tokens):
        calls[0] += 1
        if calls[0] == 1:
            raise RuntimeError("primary down")
        return "fallback_ok"

    svc._call_model = mock_call
    svc.generate("test", context=ctx, agent_name="IntentAgent", task_type="classification")

    assert ctx.get("fallback_used") is True, \
        f"expected fallback_used=True, got {ctx.get('fallback_used')}"


@test("generate() writes model_used into context['metadata']")
def _():
    from app.core.llm_service import LLMService
    from app.core.context     import create_context
    svc = LLMService()
    ctx = create_context("test")

    svc._call_model = lambda provider, model, prompt, tokens: "ok"
    svc.generate("test", context=ctx, agent_name="ExtractionAgent", task_type="extraction")

    meta = ctx.get("metadata", {})
    assert "model_used"     in meta, "metadata missing model_used"
    assert "model_provider" in meta, "metadata missing model_provider"
    assert "fallback_used"  in meta, "metadata missing fallback_used"
    assert "models_tried"   in meta, "metadata missing models_tried"
    assert isinstance(meta["models_tried"], list)


@test("models_tried in metadata lists the model that succeeded")
def _():
    from app.core.llm_service import LLMService
    from app.core.context     import create_context
    svc = LLMService()
    ctx = create_context("test")

    svc._call_model = lambda provider, model, prompt, tokens: "ok"
    svc.generate("test", context=ctx, agent_name="IntentAgent", task_type="classification")

    tried = ctx["metadata"]["models_tried"]
    assert len(tried) == 1
    assert tried[0] == ctx["model_used"]


@test("models_tried lists all failed models before successful one")
def _():
    from app.core.llm_service import LLMService
    from app.core.context     import create_context
    svc   = LLMService()
    ctx   = create_context("test")
    calls = [0]

    def mock_call(provider, model, prompt, tokens):
        calls[0] += 1
        if calls[0] < 3:
            raise RuntimeError("down")
        return "ok"

    svc._call_model = mock_call
    svc.generate("test", context=ctx, agent_name="IntentAgent", task_type="classification")

    tried = ctx["metadata"]["models_tried"]
    assert len(tried) == 3, f"expected 3 in models_tried, got {tried}"
    # Last entry is the one that succeeded
    assert tried[-1] == ctx["model_used"]


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 4. Agent integration — agent_name + task_type passed correctly ───")
# ─────────────────────────────────────────────────────────────────────────────

@test("IntentAgent passes agent_name='IntentAgent' to generate()")
def _():
    from app.agents.intent_agent import IntentAgent
    from app.core.context        import create_context

    agent = IntentAgent()
    ctx   = create_context("test message")

    captured = {}
    mock_llm  = MagicMock()

    def mock_generate(prompt, max_tokens=256, *, agent_name="", task_type="", context=None):
        captured["agent_name"] = agent_name
        captured["task_type"]  = task_type
        return '{"intent": "order"}'

    mock_llm.generate = mock_generate

    with patch("app.agents.intent_agent.get_llm", return_value=mock_llm):
        agent.execute(ctx)

    assert captured.get("agent_name") == "IntentAgent", \
        f"expected 'IntentAgent', got '{captured.get('agent_name')}'"
    assert captured.get("task_type") == "classification", \
        f"expected 'classification', got '{captured.get('task_type')}'"


@test("ExtractionAgent passes agent_name='ExtractionAgent' and task_type='extraction'")
def _():
    from app.agents.extraction_agent import ExtractionAgent
    from app.core.context            import create_context, update_context

    agent = ExtractionAgent()
    ctx   = create_context("test message")
    update_context(ctx, intent="payment")

    captured = {}
    mock_llm  = MagicMock()

    def mock_generate(prompt, max_tokens=256, *, agent_name="", task_type="", context=None):
        captured["agent_name"] = agent_name
        captured["task_type"]  = task_type
        return json.dumps({"customer": "Rahul", "amount": 500, "payment_type": None})

    mock_llm.generate = mock_generate

    with patch("app.agents.extraction_agent.get_llm", return_value=mock_llm):
        agent.execute(ctx)

    assert captured.get("agent_name") == "ExtractionAgent", \
        f"expected 'ExtractionAgent', got '{captured.get('agent_name')}'"
    assert captured.get("task_type") == "extraction", \
        f"expected 'extraction', got '{captured.get('task_type')}'"


@test("IntentAgent passes context object to generate()")
def _():
    from app.agents.intent_agent import IntentAgent
    from app.core.context        import create_context

    agent = IntentAgent()
    ctx   = create_context("test message")

    captured = {}
    mock_llm  = MagicMock()

    def mock_generate(prompt, max_tokens=256, *, agent_name="", task_type="", context=None):
        captured["context"] = context
        return '{"intent": "payment"}'

    mock_llm.generate = mock_generate

    with patch("app.agents.intent_agent.get_llm", return_value=mock_llm):
        agent.execute(ctx)

    assert captured.get("context") is ctx, \
        "IntentAgent did not pass the live context to generate()"


@test("ExtractionAgent passes context object to generate()")
def _():
    from app.agents.extraction_agent import ExtractionAgent
    from app.core.context            import create_context, update_context

    agent = ExtractionAgent()
    ctx   = create_context("test")
    update_context(ctx, intent="order")

    captured = {}
    mock_llm  = MagicMock()

    def mock_generate(prompt, max_tokens=256, *, agent_name="", task_type="", context=None):
        captured["context"] = context
        return json.dumps({"customer": None, "item": "kurti", "quantity": 3})

    mock_llm.generate = mock_generate

    with patch("app.agents.extraction_agent.get_llm", return_value=mock_llm):
        agent.execute(ctx)

    assert captured.get("context") is ctx, \
        "ExtractionAgent did not pass the live context to generate()"


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 5. Provider dispatch — NIM and OpenRouter ────────────────────────")
# ─────────────────────────────────────────────────────────────────────────────

@test("_call_nim raises RuntimeError when NVIDIA_NIM_API_KEY not set")
def _():
    from app.core.llm_service import LLMService
    svc = LLMService()
    with patch("app.core.llm_service._NIM_API_KEY", None):
        try:
            svc._call_nim("some-model", "prompt", 64)
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "NVIDIA_NIM_API_KEY" in str(e)


@test("_call_openrouter raises RuntimeError when OPENROUTER_API_KEY not set")
def _():
    from app.core.llm_service import LLMService
    svc = LLMService()
    with patch("app.core.llm_service._OPENROUTER_API_KEY", None):
        try:
            svc._call_openrouter("some-model", "prompt", 64)
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "OPENROUTER_API_KEY" in str(e)


@test("_call_model dispatches 'nim' provider to _call_nim")
def _():
    from app.core.llm_service import LLMService
    svc  = LLMService()
    seen = []

    def fake_nim(model, prompt, tokens):
        seen.append(("nim", model))
        return "nim_response"

    svc._call_nim = fake_nim
    result = svc._call_model("nim", "my-nim-model", "test", 64)
    assert result == "nim_response"
    assert seen == [("nim", "my-nim-model")]


@test("_call_model dispatches 'openrouter' provider to _call_openrouter")
def _():
    from app.core.llm_service import LLMService
    svc  = LLMService()
    seen = []

    def fake_or(model, prompt, tokens):
        seen.append(("openrouter", model))
        return "or_response"

    svc._call_openrouter = fake_or
    result = svc._call_model("openrouter", "my-or-model", "test", 64)
    assert result == "or_response"
    assert seen == [("openrouter", "my-or-model")]


@test("_call_model raises for unknown provider")
def _():
    from app.core.llm_service import LLMService
    svc = LLMService()
    try:
        svc._call_model("cohere", "cohere-model", "test", 64)
        assert False, "Should have raised"
    except RuntimeError as e:
        assert "Unknown LLM provider" in str(e)


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 6. Full pipeline — model_used visible in result ──────────────────")
# ─────────────────────────────────────────────────────────────────────────────

@test("full pipeline result context has model_used set")
def _():
    import pandas as pd
    from app.core.orchestrator import process_message

    im = MagicMock()
    em = MagicMock()

    def intent_generate(prompt, max_tokens=256, *, agent_name="", task_type="", context=None):
        if context is not None:
            context["model_used"]    = "deepseek-ai/deepseek-v3"
            context["fallback_used"] = False
        return '{"intent": "payment"}'

    def extract_generate(prompt, max_tokens=256, *, agent_name="", task_type="", context=None):
        if context is not None:
            context["model_used"]    = "deepseek-ai/deepseek-v3"
            context["fallback_used"] = False
        return json.dumps({"customer": "Rahul", "amount": 500, "payment_type": None})

    im.generate = intent_generate
    em.generate = extract_generate

    with patch("app.agents.intent_agent.get_llm",     return_value=im), \
         patch("app.agents.extraction_agent.get_llm", return_value=em), \
         patch("utils.excel_writer.append_row"), \
         patch("utils.excel_writer.read_sheet",       return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service.append_transaction",
               return_value=False):
        result = process_message("rahul ne 500 bheja")

    ctx = result["context"]
    assert "model_used" in ctx, "context missing model_used after full pipeline"


@test("full pipeline result has model_used and fallback_used keys in metadata")
def _():
    import pandas as pd
    from app.core.orchestrator import process_message

    im = MagicMock()
    em = MagicMock()

    def gen(prompt, max_tokens=256, *, agent_name="", task_type="", context=None):
        if context is not None:
            context["model_used"]    = "deepseek-ai/deepseek-v3"
            context["fallback_used"] = False
            context.setdefault("metadata", {}).update({
                "model_used": "deepseek-ai/deepseek-v3",
                "fallback_used": False,
                "models_tried": ["deepseek-ai/deepseek-v3"],
            })
        return '{"intent": "payment"}'

    im.generate = gen
    em.generate = lambda p, mt=256, **kw: json.dumps(
        {"customer": "Rahul", "amount": 500, "payment_type": None}
    )

    with patch("app.agents.intent_agent.get_llm",     return_value=im), \
         patch("app.agents.extraction_agent.get_llm", return_value=em), \
         patch("utils.excel_writer.append_row"), \
         patch("utils.excel_writer.read_sheet",       return_value=pd.DataFrame()), \
         patch("app.services.google_sheets_service.append_transaction",
               return_value=False):
        result = process_message("rahul ne 500 bheja")

    meta = result["context"].get("metadata", {})
    assert "model_used"    in meta or "model_used" in result["context"]
    assert "fallback_used" in meta or "fallback_used" in result["context"]


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 7. Failure resilience ─────────────────────────────────────────────")
# ─────────────────────────────────────────────────────────────────────────────

@test("partial failure: 1 of 3 models fails, response still returned")
def _():
    from app.core.llm_service import LLMService
    svc   = LLMService()
    calls = [0]

    def mock_call(provider, model, prompt, tokens):
        calls[0] += 1
        if calls[0] == 1:
            raise RuntimeError("first model down")
        return "second_model_ok"

    svc._call_model = mock_call
    result = svc.generate("test", agent_name="IntentAgent", task_type="classification")
    assert result == "second_model_ok"
    assert calls[0] == 2


@test("error message when all fail includes list of tried models")
def _():
    from app.core.llm_service import LLMService
    svc = LLMService()
    svc._call_model = lambda *a: (_ for _ in ()).throw(RuntimeError("down"))

    try:
        svc.generate("test")
        assert False
    except RuntimeError as e:
        err = str(e)
        assert "Tried:" in err


@test("generate() does not mutate context if no context passed")
def _():
    from app.core.llm_service import LLMService
    svc = LLMService()
    svc._call_model = lambda *a: "ok"
    # Must not raise AttributeError when context=None
    result = svc.generate("test", agent_name="IntentAgent")
    assert result == "ok"


# ─────────────────────────────────────────────────────────────────────────────
print("\n── 8. Backward compatibility ─────────────────────────────────────────")
# ─────────────────────────────────────────────────────────────────────────────

@test("generate(prompt) with no kwargs still works")
def _():
    from app.core.llm_service import LLMService
    svc = LLMService()
    svc._call_model = lambda *a: "compat"
    assert svc.generate("x") == "compat"


@test("generate(prompt, 64) positional max_tokens still works")
def _():
    from app.core.llm_service import LLMService
    svc = LLMService()
    captured = []
    svc._call_model = lambda provider, model, p, tokens: captured.append(tokens) or "ok"
    svc.generate("x", 64)
    assert captured[0] == 64


@test("get_llm() singleton returns same instance each call")
def _():
    # Reset singleton
    import app.core.llm_service as svc_mod
    svc_mod._instance = None

    from app.core.llm_service import get_llm
    a = get_llm()
    b = get_llm()
    assert a is b


@test("existing test mocks still work: mock_llm.generate.return_value pattern")
def _():
    """Verify agent mocking pattern used by test_pipeline still works."""
    from app.agents.intent_agent import IntentAgent
    from app.core.context        import create_context

    agent    = IntentAgent()
    ctx      = create_context("test")
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"intent": "payment"}'

    with patch("app.agents.intent_agent.get_llm", return_value=mock_llm):
        agent.execute(ctx)

    assert ctx["intent"] == "payment"
    # Verify generate was called (regardless of kwargs)
    mock_llm.generate.assert_called_once()


@test("demo mode run_notiflow unaffected by Phase 4 changes")
def _():
    from app.main import run_notiflow
    result = run_notiflow("rahul ne 15000 bheja", demo_mode=True)
    assert result["intent"] == "payment"
    assert result["data"]["amount"] == 15000


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