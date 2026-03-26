# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NotiFlow Autonomous** is an AI operations assistant for small businesses. It converts informal Hinglish business notifications (WhatsApp, GPay, etc.) into structured operations — payments, orders, returns, credit, and preparation tasks — powered by NVIDIA NIM with Gemini as fallback.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the FastAPI server (development)
uvicorn backend.main:app --reload

# Run the legacy CLI entry point
python app/main.py "rahul ne 15000 bheja"

# Run smoke tests (no API keys needed, uses demo mode + mocks)
python test_pipeline.py
```

## Architecture

### Entry Points
- **`backend/main.py`** — FastAPI app entry point. Routes are in `app/api/notification_routes.py`. Start with `uvicorn backend.main:app --reload`.
- **`app/main.py`** — Legacy standalone entry point (`run_notiflow()`). Kept for backward compatibility and demo/CLI use.

### Core Pipeline (`app/core/`)

```
process_message(message, source)
    ├── create_context()
    ├── build_plan()           ← Planner (app/core/planner.py)
    │       └── PlanRule list — each rule: agent key + condition + critical flag
    ├── _run_plan()            ← executes agents in planner-generated order
    ├── build_autonomy_plan()  ← AutonomyPlanner (app/core/autonomy_planner.py)
    ├── _run_autonomy()
    ├── _should_replan()       ← feedback loop (up to 2 retries if verification fails or risk=high)
    └── _build_result()
```

**Key invariants:**
- The orchestrator has zero hardcoded agent names — it resolves everything from the registry
- Adding a new agent = one entry in `AGENT_REGISTRY` + one `PlanRule` in the planner
- `LedgerAgent` is non-critical — Sheets failures never crash the pipeline

### Agent Registry (`app/core/registry.py`)
Single source of truth for all agents. `get_agent(name)` raises `KeyError` with valid keys on miss. Agents are lazily initialized on first access.

Core pipeline agents: `intent`, `extraction`, `validation`, `router`, `ledger`
Autonomy layer agents: `verification`, `monitor`, `prediction`, `urgency`, `escalation`, `recovery`

### Base Agent (`app/core/base_agent.py`)
All agents subclass `BaseAgent`. The public API is `run(context) -> context` (never `execute()` directly). `run()` handles:
- Structured logging to `context["history"]`
- Error capture → `context["errors"]` + `state="failed"`
- Re-raise so the orchestrator can decide whether to abort

### Skills (`app/skills/`)
Business logic implementations. Each skill is a standalone function (e.g., `process_order()`, `process_payment()`). Skills are invoked by `SkillRouterAgent` based on the detected intent.

Current skills: `order_skill`, `payment_skill`, `credit_skill`, `return_skill`, `preparation_skill`

### LLM Service (`app/core/llm_service.py`)
Fallback chain: **NVIDIA NIM** → **OpenRouter** → **Google Gemini**. Configured via `app/config.py`. NIM uses the OpenAI-compatible SDK.

### Context (`app/core/context.py`)
`create_context()` produces the mutable context dict passed through the entire pipeline. Keys: `message`, `intent`, `intents`, `data`, `multi_data`, `event`, `state`, `history`, `errors`, `priority`, `plan`, `metadata`.

### API Routes (`app/api/notification_routes.py`)
- `POST /api/notification` — main endpoint, calls `process_message()` and broadcasts result to all WebSocket clients
- `GET /api/notifications/generate` — generates demo notifications via Gemini
- `WebSocket /ws/notifications` — real-time streaming; accepts `{"source", "message"}` payloads
- `GET /api/stream/start` — triggers background Gemini notification stream

### Configuration (`app/config.py`)
All settings live here — no hardcoded paths or credentials elsewhere. LLM backends, sheet IDs, feature flags (`NOTIFLOW_DEMO_MODE`). Copy `.env.example` to `.env` to configure.

### Data Storage
- `data/notiflow_data.xlsx` — local Excel ledger (default, configurable via `EXCEL_FILE_PATH`)
- `skills/skill_registry.json` — skill registry
- Google Sheets as a remote ledger (optional, via `GOOGLE_SHEETS_CREDENTIALS` + `GOOGLE_SHEET_ID`)
- `data/agent_memory.json` — agent memory store

## Important Patterns

### Adding a New Agent
1. Create `app/agents/my_agent.py` — subclass `BaseAgent`, implement `execute(context) -> context`
2. Add to `AGENT_REGISTRY` in `app/core/registry.py`: `"my_agent": MyAgent()`
3. Add a `PlanRule` in `app/core/planner.py` (or `autonomy_planner.py` for the autonomy layer)
4. No changes to the orchestrator needed

### Adding a New Skill
1. Create `app/skills/my_skill.py` with a `process_my_skill(data: dict) -> dict` function
2. Register it in `app/services/skill_generator.py` or the skill registry
3. `SkillRouterAgent` will route to it based on intent

### Demo Mode
`NOTIFLOW_DEMO_MODE=true` (default) uses static canned responses — no API keys needed. Set to `false` to use live NIM inference.
