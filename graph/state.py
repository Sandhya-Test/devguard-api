from typing import Dict, List, Optional, TypedDict


class DevGuardState(TypedDict):
    request_id: str
    prompt: str
    project_id: str
    context_chunks: List[str]

    allowed: bool
    response: Optional[str]
    violations: List[str]
    policy_decisions: List[Dict]
    validation_retry_count: int
    max_validation_retries: int
    validation_retry_requested: bool
    validation_retry_reason: Optional[str]

    estimated_tokens: int
    estimated_input_tokens: int
    max_output_tokens: int
    tokens_used_request: int
    tokens_used_total: int
    tokens_remaining: int
    token_quota: int
    quota_period: str
    quota_window_key: str
    quota_window_start: str
    quota_window_end: str
    quota_date: str
    approved_quota_increase: int

    latency_ms: float
    cost_usd: float
    model_used: str

    grounding_result: Optional[Dict]
    validation_summary: Optional[Dict]
    logic_trace: Optional[Dict]
    reasoning_score: int
