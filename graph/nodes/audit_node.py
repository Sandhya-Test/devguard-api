# graph/nodes/audit_node.py
#
# Audit Node — always runs last in the pipeline.
# Responsibilities:
#   1. Build the XAI Logic Trace (the "Why" export)
#   2. Send telemetry to Azure App Insights
#   3. Write the final audit log to Cosmos DB (ONE write, here only)
 
from datetime import datetime
 
from services.audit_logger import AuditLogger
from services.telemetry import track_request, track_blocked, track_cost, track_latency
 
 
async def audit_node(state: dict):
 
    print("[Audit Node] Writing audit log...")
 
    # ──────────────────────────────────────────────────────
    # 1. Build XAI Logic Trace
    # ──────────────────────────────────────────────────────
    logic_trace = {
        "request_id":           state.get("request_id"),
        "timestamp":            datetime.utcnow().isoformat(),
        "pipeline_steps":       state.get("policy_decisions", []),
        "final_allowed":        state.get("allowed", True),
        "violations_triggered": state.get("violations", []),
        "model_used":           state.get("model_used"),
        "tokens_used_request":  state.get("tokens_used_request"),
        "tokens_used_total":    state.get("tokens_used_total"),
        "tokens_remaining":     state.get("tokens_remaining"),
        "token_quota":          state.get("token_quota"),
        "latency_ms":           state.get("latency_ms"),
        "cost_usd":             state.get("cost_usd"),
    }
 
    state["logic_trace"] = logic_trace
 
    # ──────────────────────────────────────────────────────
    # 2. Azure App Insights Telemetry
    # ──────────────────────────────────────────────────────
    project_id = state.get("project_id", "unknown")
 
    try:
        track_request(project_id)
 
        if state.get("violations"):
            for violation in state["violations"]:
                track_blocked(project_id, violation)
 
        if state.get("cost_usd") is not None:
            track_cost(project_id, state["cost_usd"])
 
        if state.get("latency_ms") is not None:
            track_latency(project_id, state["latency_ms"])
 
    except Exception as e:
        print(f"[Audit Node] Telemetry error (non-fatal): {e}")
 
    # ──────────────────────────────────────────────────────
    # 3. Cosmos DB — single write, only here
    #    llm_node no longer writes — all logging centralised here
    # ──────────────────────────────────────────────────────
    try:
        audit_logger = AuditLogger()
        await audit_logger.log_request(state)
        print("[Audit Node] Audit log stored successfully.")
 
    except Exception as e:
        print(f"[Audit Node] Cosmos write error (non-fatal): {e}")
 
    return state