import math

from services.cosmos_token_store import TokenStore

TOKEN_SAFETY_BUFFER = 32
MAX_OUTPUT_TOKEN_CAP = 2048
PROMPT_WRAPPER_TOKENS = 64


def estimate_input_tokens(prompt: str, context_chunks: list[str] | None = None) -> int:
    parts = [prompt]
    if context_chunks:
        parts.extend(context_chunks)

    combined_text = "\n".join(part for part in parts if part)
    char_estimate = math.ceil(len(combined_text) / 4) if combined_text else 1
    word_estimate = max(len(combined_text.split()) * 2, 1)
    return max(char_estimate, word_estimate) + PROMPT_WRAPPER_TOKENS


def estimate_output_tokens(prompt: str) -> int:
    words = len(prompt.split())
    prompt_lower = prompt.lower()

    heavy_keywords = [
        "3000 word",
        "5000 word",
        "research paper",
        "detailed",
        "full explanation",
        "derivations",
        "step by step",
        "comprehensive",
        "in depth",
    ]

    if any(keyword in prompt_lower for keyword in heavy_keywords):
        return 2048
    if words <= 5:
        return 128
    if words <= 20:
        return 256
    if words <= 50:
        return 512
    return 1024


def estimate_tokens(prompt: str, context_chunks: list[str] | None = None) -> int:
    return estimate_input_tokens(prompt, context_chunks) + estimate_output_tokens(prompt)


def build_output_token_cap(remaining_tokens: int, estimated_input_tokens: int) -> int:
    available_output = remaining_tokens - estimated_input_tokens - TOKEN_SAFETY_BUFFER
    if available_output <= 0:
        return 0
    return min(available_output, MAX_OUTPUT_TOKEN_CAP)


async def governance_node(state: dict):
    print("[Governance Node] Checking token quota...")

    project_id = state["project_id"]
    prompt = state["prompt"]
    context_chunks = state.get("context_chunks", [])

    estimated_input = estimate_input_tokens(prompt, context_chunks)
    estimated_total = estimate_tokens(prompt, context_chunks)
    state["estimated_tokens"] = estimated_total
    state["estimated_input_tokens"] = estimated_input

    print(f"[Governance Node] Estimated tokens: {estimated_total}")

    token_store = TokenStore()
    quota_check = await token_store.check_quota(project_id, estimated_total)
    state.update(quota_check)

    if not quota_check["allowed"]:
        quota_period = state.get("quota_period", "current")
        state["allowed"] = False
        state["violations"].append("TOKEN_QUOTA_EXCEEDED")
        state["policy_decisions"].append(
            {
                "node": "governance_node",
                "rule": "TOKEN_QUOTA",
                "action": "blocked",
            }
        )
        state["response"] = (
            f"{quota_period.capitalize()} token quota exceeded. "
            "Request blocked pending manager approval."
        )

        print("[Governance Node] Blocked by quota check.")
        return state

    max_output_tokens = build_output_token_cap(state["tokens_remaining"], estimated_input)
    state["max_output_tokens"] = max_output_tokens

    state["policy_decisions"].append(
        {
            "node": "governance_node",
            "rule": "TOKEN_QUOTA",
            "action": "allowed",
        }
    )

    print(
        "[Governance Node] Approved | "
        f"Period: {state['quota_period']} | "
        f"Remaining: {state['tokens_remaining']} | "
        f"Response cap: {state['max_output_tokens']}"
    )
    return state
