from datetime import datetime

from services.audit_logger import AuditLogger
from services.telemetry import track_blocked, track_cost, track_latency, track_request


def _build_reasoning_score(state: dict) -> int:
    score = 100
    score -= min(len(state.get("violations", [])) * 15, 60)
    if not state.get("allowed", True):
        score -= 20
    if state.get("grounding_result", {}).get("confidence") == "LOW":
        score -= 10
    return max(score, 0)


async def audit_node(state: dict):
    print("[Audit Node] Writing audit log...")

    reasoning_score = _build_reasoning_score(state)
    state["reasoning_score"] = reasoning_score

    logic_trace = {
        "request_id": state.get("request_id"),
        "timestamp": datetime.utcnow().isoformat(),
        "pipeline_steps": state.get("policy_decisions", []),
        "final_allowed": state.get("allowed", True),
        "violations_triggered": state.get("violations", []),
        "model_used": state.get("model_used"),
        "quota_period": state.get("quota_period"),
        "quota_window_key": state.get("quota_window_key"),
        "quota_window_start": state.get("quota_window_start"),
        "quota_window_end": state.get("quota_window_end"),
        "validation_retry_count": state.get("validation_retry_count"),
        "max_validation_retries": state.get("max_validation_retries"),
        "validation_retry_reason": state.get("validation_retry_reason"),
        "quota_date": state.get("quota_date"),
        "estimated_tokens": state.get("estimated_tokens"),
        "estimated_input_tokens": state.get("estimated_input_tokens"),
        "max_output_tokens": state.get("max_output_tokens"),
        "tokens_used_request": state.get("tokens_used_request"),
        "tokens_used_total": state.get("tokens_used_total"),
        "tokens_remaining": state.get("tokens_remaining"),
        "token_quota": state.get("token_quota"),
        "approved_quota_increase": state.get("approved_quota_increase"),
        "latency_ms": state.get("latency_ms"),
        "cost_usd": state.get("cost_usd"),
        "reasoning_score": reasoning_score,
        "validation_summary": state.get("validation_summary"),
    }
    state["logic_trace"] = logic_trace

    project_id = state.get("project_id", "unknown")

    try:
        track_request(project_id)
        for violation in state.get("violations", []):
            track_blocked(project_id, violation)
        if state.get("cost_usd") is not None:
            track_cost(project_id, state["cost_usd"])
        if state.get("latency_ms") is not None:
            track_latency(project_id, state["latency_ms"])
    except Exception as error:
        print(f"[Audit Node] Telemetry error (non-fatal): {error}")

    try:
        audit_logger = AuditLogger()
        await audit_logger.log_request(state)
        print("[Audit Node] Audit log stored successfully.")
    except Exception as error:
        print(f"[Audit Node] Cosmos write error (non-fatal): {error}")

    return state
