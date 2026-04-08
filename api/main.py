import logging
import os
from contextlib import asynccontextmanager
from datetime import date
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from api.middleware.request_context import generate_request_id
from graph.pipeline import run_pipeline
from services.cosmos_token_store import TokenStore

DEFAULT_MAX_VALIDATION_RETRIES = int(os.getenv("MAX_VALIDATION_RETRIES", "1"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[DevGuard] Starting up...")
    yield

    print("[DevGuard] Shutting down - flushing telemetry...")
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
    prompt: str
    project_id: str
    context_chunks: Optional[List[str]] = Field(default_factory=list)


class QuotaIncreaseRequest(BaseModel):
    additional_tokens: int = Field(gt=0)
    approved_by: str = Field(min_length=1)
    budget_date: Optional[date] = None


def _require_manager_approval_token(provided_token: Optional[str]) -> None:
    expected_token = os.getenv("MANAGER_APPROVAL_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=503,
            detail="MANAGER_APPROVAL_TOKEN is not configured.",
        )
    if provided_token != expected_token:
        raise HTTPException(
            status_code=403,
            detail="Manager approval token is invalid.",
        )


@app.post("/generate")
async def generate(request: PromptRequest):
    request_id = generate_request_id()

    state = {
        "request_id": request_id,
        "prompt": request.prompt,
        "project_id": request.project_id,
        "context_chunks": request.context_chunks or [],
        "allowed": True,
        "violations": [],
        "policy_decisions": [],
        "validation_retry_count": 0,
        "max_validation_retries": DEFAULT_MAX_VALIDATION_RETRIES,
        "validation_retry_requested": False,
        "validation_retry_reason": None,
    }

    result = await run_pipeline(state)
    return result


@app.post("/projects/{project_id}/quota/increase")
async def approve_quota_increase(
    project_id: str,
    request: QuotaIncreaseRequest,
    x_manager_approval_token: Optional[str] = Header(default=None),
):
    _require_manager_approval_token(x_manager_approval_token)
    token_store = TokenStore()

    try:
        return await token_store.approve_quota_increase(
            project_id=project_id,
            additional_tokens=request.additional_tokens,
            approved_by=request.approved_by,
            budget_date=request.budget_date.isoformat() if request.budget_date else None,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/projects/{project_id}/quota")
async def get_quota_status(project_id: str, budget_date: Optional[date] = None):
    token_store = TokenStore()
    return await token_store.check_quota(
        project_id=project_id,
        estimated_tokens=0,
        budget_date=budget_date.isoformat() if budget_date else None,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "DevGuard AI Gateway"}
