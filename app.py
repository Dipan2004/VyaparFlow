# app.py for Hugging Face Spaces (VyaparFlow)
import uvicorn

if __name__ == "__main__":
    # Launch FastAPI app from backend.main:app on port 7860 (required by HF)
    uvicorn.run("backend.main:app", host="0.0.0.0", port=7860)
