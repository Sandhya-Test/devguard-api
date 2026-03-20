# policies/source_grounding.py
#
# Source Grounding Check (RAG-specific)
# ───────────────────────────────────────
# If the developer passes context_chunks in the state,
# this policy requires the LLM response to reference that context.
# If the response ignores the context entirely → flagged as LOW_CONFIDENCE.
 
from services.azure_openai import call_llm
 
 
async def check_source_grounding(prompt: str, response: str, context_chunks: list) -> dict:
    """
    Validates that the LLM response is grounded in the provided context chunks.
 
    Returns:
        {
            "grounded": bool,
            "confidence": "HIGH" | "MEDIUM" | "LOW",
            "reason": str
        }
    """
 
    if not context_chunks:
        # No RAG context provided — skip grounding check
        return {
            "grounded": True,
            "confidence": "HIGH",
            "reason": "No context chunks provided — grounding check skipped."
        }
 
    context_text = "\n\n".join(
        [f"[Chunk {i+1}]: {chunk}" for i, chunk in enumerate(context_chunks)]
    )
 
    grounding_prompt = f"""
You are a fact-checking assistant.
 
The following CONTEXT was provided to an AI system:
{context_text}
 
The AI generated this RESPONSE to the user's question:
"{response}"
 
Task:
1. Does the response reference or draw from the provided context?
2. Does it introduce facts NOT found in the context?
 
Answer ONLY in this exact format:
GROUNDED: YES or NO
CONFIDENCE: HIGH, MEDIUM, or LOW
REASON: one sentence explanation
"""
 
    result, _ = await call_llm(grounding_prompt)
 
    # Parse result
    grounded   = "GROUNDED: YES" in result.upper()
    confidence = "HIGH"
 
    if "CONFIDENCE: LOW"    in result.upper():
        confidence = "LOW"
    elif "CONFIDENCE: MEDIUM" in result.upper():
        confidence = "MEDIUM"
 
    reason = "Unable to parse reason."
    for line in result.splitlines():
        if line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[-1].strip()
            break
 
    return {
        "grounded":   grounded,
        "confidence": confidence,
        "reason":     reason,
    }