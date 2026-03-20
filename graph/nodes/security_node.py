# graph/nodes/security_node.py
#
# Security Node — first gate in the pipeline.
# Two checks:
#   1. Prompt Injection Detection (pattern matching)
#   2. Input Content Safety (Azure AI Content Safety API)
#      Catches harmful input like self-harm, violence, hate
#      BEFORE it ever reaches the LLM.
 
from services.content_safety import check_content_safety
 
PROMPT_INJECTION_PATTERNS = [
    # Core patterns
    "ignore previous instructions",
    "system prompt",
    "bypass safety",
    # Extended real-world variants
    "ignore all previous",
    "disregard instructions",
    "disregard all previous",
    "forget your instructions",
    "forget previous instructions",
    "you are now",
    "act as",
    "act as if",
    "pretend you are",
    "pretend to be",
    "jailbreak",
    "new persona",
    "override instructions",
    "override your",
    "ignore your",
    "ignore the above",
    "do not follow",
    "do anything now",
    "dan mode",
    "developer mode",
    "unrestricted mode",
    "maintenance mode",
    "admin override",
    "sudo mode",
    "you have no restrictions",
    "without restrictions",
    "no restrictions",
    "ignore ethics",
    "ignore safety",
    "reveal your instructions",
    "reveal your system",
    "show your prompt",
    "print your instructions",
    "output your instructions",
]
 
 
async def security_node(state: dict):
 
    prompt = state["prompt"]
    prompt_lower = prompt.lower()
 
    # ──────────────────────────────────────────────────────
    # Check 1: Prompt Injection Detection
    # ──────────────────────────────────────────────────────
    for pattern in PROMPT_INJECTION_PATTERNS:
 
        if pattern in prompt_lower:
 
            print(f"[Security Node] Injection detected: '{pattern}'")
 
            state["allowed"] = False
            state["violations"].append("PROMPT_INJECTION")
            state["policy_decisions"].append({
                "node":    "security_node",
                "rule":    "PROMPT_INJECTION",
                "action":  "blocked",
                "matched": pattern
            })
            state["response"] = "Prompt injection detected. Request blocked."
            return state
 
    # ──────────────────────────────────────────────────────
    # Check 2: Input Content Safety
    # Screens harmful content (self-harm, violence, hate, sexual)
    # BEFORE it reaches the LLM — avoids wasting tokens on
    # content that will be blocked anyway.
    # ──────────────────────────────────────────────────────
    input_safe = await check_content_safety(prompt)
 
    if not input_safe:
 
        print("[Security Node] Input content safety triggered.")
 
        state["allowed"] = False
        state["violations"].append("INPUT_CONTENT_BLOCKED")
        state["policy_decisions"].append({
            "node":   "security_node",
            "rule":   "INPUT_CONTENT_SAFETY",
            "action": "blocked"
        })
        state["response"] = "Input blocked by Content Safety policy."
        return state
 
    # ── All checks passed ──
    state["policy_decisions"].append({
        "node":   "security_node",
        "rule":   "PROMPT_INJECTION",
        "action": "allowed"
    })
    state["policy_decisions"].append({
        "node":   "security_node",
        "rule":   "INPUT_CONTENT_SAFETY",
        "action": "allowed"
    })
 
    print("[Security Node] Passed all checks.")
    return state