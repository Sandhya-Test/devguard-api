# graph/state.py
 
from typing import TypedDict, List, Dict, Optional, Any
 
 
class DevGuardState(TypedDict):
 
    # ── Request Identity ──
    request_id: str
    prompt:     str
    project_id: str
 
    # ── RAG Context (optional) ──
    context_chunks: List[str]      # populated by developer for RAG apps
 
    # ── Policy Gate ──
    allowed:    bool
    response:   Optional[str]
    violations: List[str]
 
    # ── Policy Trace ──
    policy_decisions: List[Dict]
 
    # ── Token Tracking ──
    estimated_tokens:    int
    tokens_used_request: int
    tokens_used_total:   int
    tokens_remaining:    int
    token_quota:         int
 
    # ── Performance ──
    latency_ms: float
    cost_usd:   float
 
    # ── Model Info ──
    model_used: str          # set by model tiering
 
    # ── Validation Results ──
    grounding_result: Optional[Dict]   # set by source grounding check
 
    # ── XAI Logic Trace ──
    logic_trace: Optional[Dict]        # set by audit node