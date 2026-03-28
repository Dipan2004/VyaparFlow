# =============================================================================
# VyaparFlow - Hugging Face Spaces Deployment Guide
# =============================================================================

## 📋 Project Overview

**VyaparFlow** is an AI-powered business operations assistant that:
- Processes informal Hinglish business notifications
- Extracts structured data (orders, payments, returns, credits)
- Integrates with Excel and Google Sheets
- Powered by NVIDIA NIM (DeepSeek models)

### Tech Stack
- **Backend:** FastAPI + Uvicorn (Python 3.13)
- **Frontend:** React + Vite + TypeScript (bundled)
- **LLM:** NVIDIA NIM (DeepSeek), with Gemini fallback
- **Data:** pandas, openpyxl, gspread
- **Container:** Docker (optimized for Hugging Face Spaces)

---

## 🚀 Deployment Process

### Step 1: Create Hugging Face Space
```bash
1. Go to https://huggingface.co/spaces
2. Click "Create new Space"
3. Name: vyaparflow
4. License: Apache 2.0
5. Space SDK: Docker
6. Visibility: Public/Private
```

### Step 2: Push Code to Hugging Face
```bash
# Clone the space repository
git clone https://huggingface.co/spaces/YOUR_USERNAME/vyaparflow

# Copy VyaparFlow code (excluding venv)
cp -r /path/to/VyaparFlow/* vyaparflow/

# Important: Keep only these directories:
# ✅ app/
# ✅ backend/
# ✅ services/
# ✅ skills/
# ✅ models/
# ✅ prompts/
# ✅ utils/
# ✅ validators/
# ✅ data/ (empty directory)
# ✅ credentials/ (empty directory)

# Remove unnecessary:
# ❌ Denv/ (your local virtual environment)
# ❌ venv/
# ❌ frontend/node_modules/
# ❌ __pycache__/
# ❌ *.pyc

cd vyaparflow
git add .
git commit -m "Add VyaparFlow backend for Hugging Face Spaces"
git push
```

### Step 3: Configure Secrets in Hugging Face
Go to Space Settings → Secrets & variables, add:

```
NOTIFLOW_DEMO_MODE = true  # Start with demo mode
NVIDIA_NIM_API_KEY = (your actual API key)
NVIDIA_NIM_BASE_URL = https://integrate.api.nvidia.com/v1
NIM_PRIMARY_MODEL = deepseek-ai/deepseek-v3.2
GEMINI_API_KEY = (optional fallback)
OPENROUTER_API_KEY = (optional secondary fallback)
```

---

## 📝 File Structure

```
vyaparflow/
├── Dockerfile              # Multi-stage build for HF
├── .dockerignore          # Excludes venv, __pycache__, etc.
├── requirements.txt       # Python dependencies
├── app/
│   ├── main.py           # Entry point (API + CLI)
│   ├── config.py         # Centralized config (from .env)
│   ├── api/              # FastAPI routes
│   ├── core/             # Orchestration logic
│   ├── agents/           # Multi-agent system
│   ├── memory/           # State management
│   ├── services/         # External integrations
│   ├── skills/           # Business logic
│   └── utils/            # Helpers
├── backend/
│   └── main.py           # FastAPI app (uvicorn entry)
├── data/
│   ├── notiflow_data.xlsx        # Auto-created
│   └── agent_memory.json         # Auto-created
├── credentials/
│   └── sheets.json       # (User-provided, not in repo)
└── .env                  # Configuration (secrets masked in HF)
```

---

## 🔌 API Endpoints

### Health Check
```bash
curl https://YOUR_SPACE.hf.space/health
# Response:
{
  "status": "ok",
  "demo_mode": true,
  "nim_model": "deepseek-ai/deepseek-v3.2",
  "nim_enabled": true,
  "gemini_enabled": false,
  "excel_file": "/app/data/notiflow_data.xlsx"
}
```

### Process Message (Core Endpoint)
```bash
curl -X POST "https://YOUR_SPACE.hf.space/process" \
  -H "Content-Type: application/json" \
  -d '{"message": "rahul ne 15000 bheja"}'
```

### API Documentation
- **Swagger UI:** `https://YOUR_SPACE.hf.space/docs`
- **ReDoc:** `https://YOUR_SPACE.hf.space/redoc`

---

## 🐳 Docker Details

### Port Configuration
- **Hugging Face requirement:** Port 7860 (fixed, cannot change)
- **Dockerfile:** Exposes port 7860
- **Command:** `uvicorn backend.main:app --host 0.0.0.0 --port 7860`

### Multi-stage Build
```dockerfile
Stage 1 (Builder):
  - Python 3.13-slim
  - Install build tools
  - Pip install all requirements
  - Result: /root/.local (wheels)

Stage 2 (Runtime):
  - Python 3.13-slim (smaller)
  - Copy wheels from Stage 1
  - Copy project code
  - Result: ~400MB image (vs 1.2GB if single-stage)
```

### Health Check
- **Interval:** 30 seconds
- **Timeout:** 10 seconds
- **Endpoint:** `GET /health`
- **Success:** HTTP 200

### .dockerignore Content
Excludes 50+ patterns:
- Virtual environments (venv/, Denv/, ENV/)
- Cache files (__pycache__/, *.pyc)
- Node modules (node_modules/, frontend build)
- Test files (test_*.py, *.ipynb)
- IDE files (.vscode/, .idea/)
- Large files (*.zip, *.tar.gz)
- Credentials (credentials/, *.pem, *.key)
- Temp/log files (*.log, tmp/, temp/)

---

## 🔑 Environment Variables

### Required for Live Mode
```
NOTIFLOW_DEMO_MODE=false
NVIDIA_NIM_API_KEY=your_api_key
```

### Optional (Fallback)
```
GEMINI_API_KEY=fallback_key
OPENROUTER_API_KEY=secondary_fallback_key
GOOGLE_SHEETS_CREDENTIALS=credentials/sheets.json
```

---

## ✅ Pre-deployment Checklist

- [ ] Remove all virtual environment folders (Denv/, venv/)
- [ ] Delete `__pycache__/` directories
- [ ] No hardcoded API keys in code (use .env)
- [ ] requirements.txt is up-to-date
- [ ] Dockerfile and .dockerignore are present
- [ ] .env has Hugging Face compatible settings
- [ ] All imports use relative paths
- [ ] Health endpoint returns valid JSON
- [ ] No external file writes outside /app/data

---

## 🛠️ Troubleshooting

### Container won't start
```bash
# Check logs in Hugging Face Space
# Error: "Port X is already in use"
# → Dockerfile uses port 7860 ✅

# Error: "ModuleNotFoundError"
# → Check requirements.txt includes all imports
```

### API Health Check Fails
```bash
# Missing .env variables?
# → Check Space Secrets are set correctly

# Import error?
# → Check PYTHONPATH includes project root
```

### Slow Response Times
```bash
# Demo mode enabled? (use mock responses)
# → Set NOTIFLOW_DEMO_MODE=true initially

# Rate limit hit?
# → Add API backoff/retry logic
# → Use OPENROUTER_API_KEY as fallback
```

---

## 📈 Performance Notes

- **Build time:** ~2 minutes (first build, multi-stage)
- **Image size:** ~400MB (optimized)
- **Startup time:** ~30 seconds
- **Memory usage:** ~300-500MB (depends on model loaded)

---

## 🔒 Security Notes

⚠️ **NEVER commit .env with real API keys** ⚠️

Use Hugging Face Secrets:
1. Don't add NVIDIA_NIM_API_KEY to repo
2. Add it as a Secret in Space Settings
3. HF injects as environment variable at runtime

---

## 💡 Next Steps

1. ✅ Build Docker image locally:
   ```bash
   docker build -t vyaparflow:latest .
   docker run -p 7860:7860 vyaparflow:latest
   ```

2. ✅ Test API locally: `curl http://localhost:7860/health`

3. ✅ Push to Hugging Face Space

4. ✅ Monitor logs in Space dashboard

5. ✅ Share URL: `https://huggingface.co/spaces/YOUR_USERNAME/vyaparflow`

---

## 📚 Documentation Links

- [Hugging Face Spaces Docker Docs](https://huggingface.co/docs/hub/spaces-config-reference#docker)
- [FastAPI on Hugging Face](https://huggingface.co/docs/hub/spaces-run-private)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)

---

**VyaparFlow** © 2026 — Ready for production! 🚀
