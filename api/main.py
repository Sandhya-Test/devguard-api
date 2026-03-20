# api/main.py
 
import logging
from contextlib import asynccontextmanager
from typing import List, Optional
 
from fastapi import FastAPI
from pydantic import BaseModel
 
from graph.pipeline import run_pipeline
from api.middleware.request_context import generate_request_id
 
 
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and graceful shutdown.
    Calls telemetry.flush() on exit to cleanly close the
    aiohttp session opened by AzureLogHandler — fixes the
    'Unclosed client session' warning from opencensus.
    """
    # ── Startup ──
    print("[DevGuard] Starting up...")
    yield
 
    # ── Shutdown — flush telemetry first, then close logging ──
    print("[DevGuard] Shutting down — flushing telemetry...")
    try:
        from services.telemetry import flush
        flush()
    except Exception:
        pass
    logging.shutdown()
    print("[DevGuard] Shutdown complete.")
 
 
app = FastAPI(
    title="DevGuard AI Gateway",
    description="Policy-as-Code layer for Azure OpenAI",
    version="1.0.0",
    lifespan=lifespan,
)
 
 
class PromptRequest(BaseModel):
    prompt:         str
    project_id:     str
    context_chunks: Optional[List[str]] = []
 
 
@app.post("/generate")
async def generate(request: PromptRequest):
 
    request_id = generate_request_id()
 
    state = {
        "request_id":       request_id,
        "prompt":           request.prompt,
        "project_id":       request.project_id,
        "context_chunks":   request.context_chunks or [],
        "allowed":          True,
        "violations":       [],
        "policy_decisions": []
    }
 
    result = await run_pipeline(state)
 
    return result
 
 
@app.get("/health")
async def health():
    return {"status": "ok", "service": "DevGuard AI Gateway"}