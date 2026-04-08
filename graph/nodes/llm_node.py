import asyncio
import time

from openai import BadRequestError

from policies.model_tiering import select_model
from policies.pii_redactor import redact_pii
from services.azure_openai import call_llm
from services.content_safety import check_content_safety
from services.cosmos_token_store import TokenStore
from utils.cost_calculator import calculate_cost


def _get_timeout(model: str) -> int:
    return 90 if "mini" in model else 120


def _is_content_filter_error(error: BadRequestError) -> bool:
    message = str(error).lower()
    markers = (
        "content_filter",
        "content filter",
        "content management policy",
        "responsible ai",
        "safety system",
    )
    return any(marker in message for marker in markers)


async def llm_node(state: dict):
    if not state.get("allowed", True):
        return state

    print("[LLM Node] Preparing LLM request...")

    selected_model = select_model(state["prompt"])
    state["model_used"] = selected_model
    timeout_seconds = _get_timeout(selected_model)

    prompt = state["prompt"]
    context_chunks = state.get("context_chunks", [])
    max_output_tokens = state.get("max_output_tokens")
    retry_reason = state.get("validation_retry_reason")
    retry_count = int(state.get("validation_retry_count", 0))
    is_validation_retry = bool(state.get("validation_retry_requested"))
    previous_response = state.get("response")

    if is_validation_retry:
        state["validation_retry_requested"] = False

    if max_output_tokens is not None and max_output_tokens <= 0:
        quota_period = state.get("quota_period", "current")
        print("[LLM Node] No response budget left for this request.")
        state["allowed"] = False
        state["violations"].append("TOKEN_QUOTA_EXCEEDED")
        state["policy_decisions"].append(
            {"node": "llm_node", "rule": "TOKEN_QUOTA", "action": "blocked"}
        )
        state["response"] = (
            f"{quota_period.capitalize()} token quota exceeded. "
            "Request blocked pending manager approval."
        )
        return state

    if context_chunks:
        context_text = "\n".join(context_chunks)
        final_prompt = f"""
You MUST answer ONLY using the provided context.

Context:
{context_text}

Question:
{prompt}

Strict Rules:
- Use ONLY the given context
- Do NOT add external knowledge
- Do NOT generalize
- Keep answer precise and factual
"""
    else:
        final_prompt = prompt

    if retry_reason:
        retry_feedback = f"""

Validation Feedback:
- Previous answer failed validation on retry attempt {retry_count}.
- Reason: {retry_reason}

Required Fix:
- Regenerate the answer more carefully.
- Remove unsupported claims.
- If the available information is insufficient, say so explicitly instead of guessing.
"""
        if previous_response:
            retry_feedback += f"""

Previous Answer:
{previous_response}
"""
        final_prompt = f"{final_prompt}{retry_feedback}"

    print("[LLM Node] Calling Azure OpenAI...")
    start_time = time.time()

    try:
        content, tokens_used = await asyncio.wait_for(
            call_llm(final_prompt, model=selected_model, max_tokens=max_output_tokens),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        print(f"[LLM Node] Timeout after {timeout_seconds}s - blocking.")
        state["allowed"] = False
        state["violations"].append("LATENCY_EXCEEDED")
        state["policy_decisions"].append(
            {"node": "llm_node", "rule": "LATENCY_GUARD", "action": "blocked"}
        )
        state["response"] = "LLM timeout protection triggered."
        state["latency_ms"] = int((time.time() - start_time) * 1000)
        return state
    except BadRequestError as error:
        state["allowed"] = False
        state["latency_ms"] = int((time.time() - start_time) * 1000)

        if _is_content_filter_error(error):
            print("[LLM Node] Azure OpenAI content filter triggered.")
            state["violations"].append("AZURE_CONTENT_FILTER")
            state["policy_decisions"].append(
                {"node": "llm_node", "rule": "AZURE_CONTENT_FILTER", "action": "blocked"}
            )
            state["response"] = "Request blocked by Azure OpenAI safety policy."
            return state

        print(f"[LLM Node] Invalid LLM request: {error}")
        state["violations"].append("LLM_REQUEST_INVALID")
        state["policy_decisions"].append(
            {"node": "llm_node", "rule": "LLM_REQUEST_VALIDATION", "action": "error"}
        )
        state["response"] = "LLM request failed due to configuration or request validation error."
        return state

    latency_ms = int((time.time() - start_time) * 1000)
    state["latency_ms"] = latency_ms
    state["tokens_used_request"] = tokens_used
    state["cost_usd"] = calculate_cost(tokens_used, model=selected_model)

    token_store = TokenStore()
    usage = await token_store.update_tokens(
        state["project_id"],
        tokens_used,
        budget_date=state.get("quota_date"),
    )
    state.update(usage)

    output_safe = await check_content_safety(content)
    if not output_safe:
        print("[LLM Node] Outbound content blocked.")
        state["allowed"] = False
        state["violations"].append("OUTBOUND_CONTENT_BLOCKED")
        state["policy_decisions"].append(
            {"node": "llm_node", "rule": "OUTBOUND_CONTENT_SAFETY", "action": "blocked"}
        )
        state["response"] = "Response blocked by Content Safety."
        return state

    state["response"] = redact_pii(content)
    state["policy_decisions"].append(
        {"node": "llm_node", "rule": "FINAL_RESPONSE", "action": "allowed"}
    )

    print(
        f"[LLM Node] Done | Model: {selected_model} | Tokens: {tokens_used} | "
        f"Latency: {latency_ms}ms | Cost: ${state['cost_usd']}"
    )
    return state
