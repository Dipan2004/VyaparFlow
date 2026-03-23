# NotiFlow Autonomous — Migration Guide (v1 → v2)

## What Changed

| Area | v1 (original) | v2 (autonomous) |
|---|---|---|
| LLM backend | AWS Bedrock (Nova Lite) | NVIDIA NIM → Gemini fallback |
| State passing | Scattered function args | Unified `context` dict |
| Agent structure | Standalone modules | `BaseAgent` subclasses |
| Orchestrator | Manual stage calls | Context-driven pipeline |
| Import layout | Flat root-level | `app/` package tree |

---

## Step 1 — Update `.env`

Remove all AWS variables. Add NIM key:

```env
# REMOVE THESE:
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...
# AWS_DEFAULT_REGION=...

# ADD THESE:
NVIDIA_NIM_API_KEY=your_key_here
NVIDIA_NIM_MODEL=meta/llama-3.1-8b-instruct      # optional override
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1  # optional override

# KEEP THESE (unchanged):
GEMINI_API_KEY=your_gemini_key          # fallback — still used
GOOGLE_SHEETS_CREDENTIALS=credentials/sheets.json
GOOGLE_SHEET_ID=your_sheet_id
NOTIFLOW_DEMO_MODE=true
```

---

## Step 2 — Install new dependencies

```bash
pip uninstall boto3 botocore -y
pip install openai>=1.30.0
pip install -r requirements.txt
```

---

## Step 3 — Delete obsolete files

```bash
# From your project root:
rm app/bedrock_client.py
rm agent/model_router.py
```

---

## Step 4 — Apply new folder structure

Move files into the new layout (or use the output bundle directly):

```
app/
├── core/
│   ├── __init__.py
│   ├── llm_service.py        ← NEW  replaces bedrock_client + model_router
│   ├── context.py            ← NEW  unified request context
│   ├── base_agent.py         ← NEW  BaseAgent interface
│   └── orchestrator.py       ← NEW  context-driven pipeline
├── agents/
│   ├── __init__.py
│   ├── intent_agent.py       ← NEW  wraps old intent logic
│   ├── extraction_agent.py   ← NEW  wraps old extraction logic
│   ├── validation_agent.py   ← NEW  wraps data_validator
│   ├── skill_router_agent.py ← NEW  wraps router.py
│   └── ledger_agent.py       ← NEW  wraps google_sheets_service
├── services/                 ← MOVED (unchanged logic)
├── skills/                   ← MOVED (unchanged logic)
├── validators/               ← MOVED (unchanged logic)
├── memory/                   ← MOVED (unchanged logic)
└── utils/                    ← MOVED (unchanged logic)
```

Compatibility shims at the old import paths (`agent/`, `services/`,
`skills/`, etc.) ensure any code you haven't migrated yet continues
to work without modification.

---

## Step 5 — Start the server

```bash
uvicorn backend.main:app --reload
```

Health check:
```bash
curl http://localhost:8000/health
# {
#   "status": "ok",
#   "demo_mode": true,
#   "nim_model": "meta/llama-3.1-8b-instruct",
#   "nim_enabled": false,   ← true once NVIDIA_NIM_API_KEY is set
#   "gemini_enabled": false
# }
```

---

## Step 6 — Test demo mode (no API keys needed)

```bash
NOTIFLOW_DEMO_MODE=true python app/main.py "rahul ne 15000 bheja"
# {
#   "message": "rahul ne 15000 bheja",
#   "intent": "payment",
#   "data": {"customer": "Rahul", "amount": 15000, "payment_type": null},
#   "event": {"event": "payment_recorded", ...},
#   "sheet_updated": false
# }
```

---

## Step 7 — Test live mode (NIM key required)

```bash
NOTIFLOW_DEMO_MODE=false python app/main.py "bhaiya 3 kurti bhej dena"
```

The pipeline now flows through the full agent chain:

```
create_context()
  → IntentAgent.run(ctx)       [NIM → Gemini fallback]
  → ExtractionAgent.run(ctx)   [NIM → Gemini fallback]
  → ValidationAgent.run(ctx)   [pure Python, no LLM]
  → SkillRouterAgent.run(ctx)  [dispatches to skill]
  → LedgerAgent.run(ctx)       [Google Sheets, non-fatal]
```

---

## Backward Compatibility

All existing API consumers are unaffected:

- `POST /api/notification` — identical request/response shape
- `GET /api/notifications/generate` — unchanged
- `WebSocket /ws/notifications` — unchanged
- `run_notiflow(message)` — identical return shape

The only visible addition is an optional `"context"` key in the live-mode
response which exposes the full pipeline context for debugging.

---

## Adding a New Agent (Phase 2+)

```python
# app/agents/my_new_agent.py
from app.core.base_agent import BaseAgent
from app.core.context import update_context

class MyNewAgent(BaseAgent):
    name = "MyNewAgent"

    def execute(self, context):
        # read from context, do work, write back
        context["data"]["my_field"] = "computed_value"
        update_context(context, state="my_stage_done")
        return context
```

Then register it in `app/core/orchestrator.py`:

```python
from app.agents.my_new_agent import MyNewAgent

_PIPELINE = [IntentAgent, ExtractionAgent, ValidationAgent,
             MyNewAgent,                    # ← insert here
             SkillRouterAgent]
```

That's it. No other changes needed.
