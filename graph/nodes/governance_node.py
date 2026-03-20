# graph/nodes/governance_node.py

from services.cosmos_token_store import TokenStore


def estimate_tokens(prompt: str):
    """
    Smart + intent-aware token estimation
    Prevents underestimation for large prompts
    """

    words = len(prompt.split())
    prompt_lower = prompt.lower()

    # Approx input tokens
    input_tokens = int(words * 1.3)

    # 🚨 Detect heavy / expensive prompts
    heavy_keywords = [
        "3000 word", "5000 word", "research paper",
        "detailed", "full explanation", "derivations",
        "step by step", "comprehensive", "in depth"
    ]

    if any(keyword in prompt_lower for keyword in heavy_keywords):
        output_tokens = 2000  # 🔥 aggressive estimate

    elif words <= 5:
        output_tokens = 20
    elif words <= 20:
        output_tokens = 50
    elif words <= 50:
        output_tokens = 150
    else:
        output_tokens = 400

    return input_tokens + output_tokens


async def governance_node(state: dict):

    print("[Governance Node] Checking token quota...")

    project_id = state["project_id"]
    prompt     = state["prompt"]

    token_store = TokenStore()

    # ─────────────────────────────
    # Estimate tokens BEFORE LLM
    # ─────────────────────────────
    estimated_total = estimate_tokens(prompt)

    print(f"[Governance Node] Estimated tokens: {estimated_total}")

    # ─────────────────────────────
    # Predictive quota check
    # ─────────────────────────────
    quota_check = await token_store.check_quota(
        project_id,
        estimated_total
    )

    state.update(quota_check)

    # ─────────────────────────────
    # BLOCK if quota exceeded
    # ─────────────────────────────
    if not quota_check["allowed"]:

        state["allowed"] = False
        state["violations"].append("TOKEN_QUOTA_EXCEEDED")

        state["policy_decisions"].append({
            "node": "governance_node",
            "rule": "TOKEN_QUOTA",
            "action": "blocked"
        })

        state["response"] = "Token quota exceeded (predicted). Request blocked."

        print("[Governance Node] Blocked by predictive quota check.")

        return state

    # ─────────────────────────────
    # Allowed path
    # ─────────────────────────────
    state["policy_decisions"].append({
        "node": "governance_node",
        "rule": "TOKEN_QUOTA",
        "action": "allowed"
    })

    print(
        f"[Governance Node] Approved | Remaining: {state['tokens_remaining']}"
    )

    return state