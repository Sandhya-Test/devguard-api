# graph/builder.py
 
from langgraph.graph import StateGraph, END
 
from graph.state import DevGuardState
from graph.nodes.security_node import security_node
from graph.nodes.governance_node import governance_node
from graph.nodes.llm_node import llm_node
from graph.nodes.validation_node import validation_node
from graph.nodes.audit_node import audit_node
 
 
# ---------------------------------------------------
# Routing Functions
# ---------------------------------------------------
 
def route_after_security(state: DevGuardState):
    if not state.get("allowed", True):
        return "audit"
    return "governance"
 
 
def route_after_governance(state: DevGuardState):
    if not state.get("allowed", True):
        return "audit"
    return "llm"
 
 
def route_after_llm(state: DevGuardState):
    if not state.get("allowed", True):
        return "audit"
    return "validation"
 
 
def route_after_validation(state: DevGuardState):
    # Always go to audit — whether blocked or passed
    return "audit"
 
 
# ---------------------------------------------------
# Graph Builder
# ---------------------------------------------------
 
def build_graph():
 
    builder = StateGraph(DevGuardState)
 
    # Register all nodes
    builder.add_node("security",   security_node)
    builder.add_node("governance", governance_node)
    builder.add_node("llm",        llm_node)
    builder.add_node("validation", validation_node)
    builder.add_node("audit",      audit_node)
 
    # Entry point
    builder.set_entry_point("security")
 
    # security → governance | audit
    builder.add_conditional_edges(
        "security",
        route_after_security,
        {
            "governance": "governance",
            "audit":      "audit",
        },
    )
 
    # governance → llm | audit
    builder.add_conditional_edges(
        "governance",
        route_after_governance,
        {
            "llm":   "llm",
            "audit": "audit",
        },
    )
 
    # llm → validation | audit
    builder.add_conditional_edges(
        "llm",
        route_after_llm,
        {
            "validation": "validation",
            "audit":      "audit",
        },
    )
 
    # validation → audit (always)
    builder.add_conditional_edges(
        "validation",
        route_after_validation,
        {
            "audit": "audit",
        },
    )
 
    # audit → END (always)
    builder.add_edge("audit", END)
 
    return builder.compile()