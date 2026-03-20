# graph/pipeline.py
 
from graph.nodes.security_node   import security_node
from graph.nodes.governance_node import governance_node
from graph.nodes.llm_node        import llm_node
from graph.nodes.validation_node import validation_node
from graph.nodes.audit_node      import audit_node
 
 
async def run_pipeline(state: dict):
 
    # 1. Security Gate
    state = await security_node(state)
    if not state.get("allowed", True):
        state = await audit_node(state)
        return state
 
    # 2. Governance Gate
    state = await governance_node(state)
    if not state.get("allowed", True):
        state = await audit_node(state)
        return state
 
    # 3. LLM Call
    state = await llm_node(state)
    if not state.get("allowed", True):
        state = await audit_node(state)
        return state
 
    # 4. Validation (Hallucination Check)
    state = await validation_node(state)
 
    # 5. Audit (always runs — blocked or passed)
    state = await audit_node(state)
 
    return state