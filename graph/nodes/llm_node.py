# graph/nodes/llm_node.py

import time
import asyncio
from openai import BadRequestError

from services.azure_openai import call_llm
from services.cosmos_token_store import TokenStore
from services.content_safety import check_content_safety
from policies.pii_redactor import redact_pii
from policies.model_tiering import select_model
from utils.cost_calculator import calculate_cost


def _get_timeout(model: str) -> int:
    """
    Increased timeout for stability
    """
    return 90 if "mini" in model else 120


async def llm_node(state: dict):

    if not state.get("allowed", True):
        return state

    print("[LLM Node] Preparing LLM request...")

    # ── Model Selection ──
    selected_model = select_model(state["prompt"])
    state["model_used"] = selected_model
    timeout_seconds = _get_timeout(selected_model)

    # ──────────────────────────────────────
    # 🔥 CONTEXT INJECTION (CRITICAL FIX)
    # ──────────────────────────────────────
    prompt = state["prompt"]
    context_chunks = state.get("context_chunks", [])

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

    print("[LLM Node] Calling Azure OpenAI...")

    start_time = time.time()

    try:
        content, tokens_used = await asyncio.wait_for(
            call_llm(final_prompt, model=selected_model),
            timeout=timeout_seconds
        )

    except asyncio.TimeoutError:
        print(f"[LLM Node] Timeout after {timeout_seconds}s — blocking.")

        state["allowed"] = False
        state["violations"].append("LATENCY_EXCEEDED")

        state["policy_decisions"].append({
            "node": "llm_node",
            "rule": "LATENCY_GUARD",
            "action": "blocked"
        })

        state["response"] = "LLM timeout protection triggered."
        state["latency_ms"] = int((time.time() - start_time) * 1000)

        return state

    except BadRequestError:
        print("[LLM Node] Azure OpenAI content filter triggered.")

        state["allowed"] = False
        state["violations"].append("AZURE_CONTENT_FILTER")

        state["policy_decisions"].append({
            "node": "llm_node",
            "rule": "AZURE_CONTENT_FILTER",
            "action": "blocked"
        })

        state["response"] = "Request blocked by Azure OpenAI safety policy."
        state["latency_ms"] = int((time.time() - start_time) * 1000)

        return state

    # ──────────────────────────────────────
    # Record Metrics
    # ──────────────────────────────────────
    latency_ms = int((time.time() - start_time) * 1000)

    state["latency_ms"] = latency_ms
    state["tokens_used_request"] = tokens_used

    # ── Cost Calculation ──
    cost = calculate_cost(tokens_used, model=selected_model)
    state["cost_usd"] = cost

    # ──────────────────────────────────────
    # Token Update (AFTER LLM)
    # ──────────────────────────────────────
    token_store = TokenStore()
    usage = await token_store.update_tokens(state["project_id"], tokens_used)
    state.update(usage)

    # ──────────────────────────────────────
    # Outbound Content Safety
    # ──────────────────────────────────────
    output_safe = await check_content_safety(content)

    if not output_safe:
        print("[LLM Node] Outbound content blocked.")

        state["allowed"] = False
        state["violations"].append("OUTBOUND_CONTENT_BLOCKED")

        state["policy_decisions"].append({
            "node": "llm_node",
            "rule": "OUTBOUND_CONTENT_SAFETY",
            "action": "blocked"
        })

        state["response"] = "Response blocked by Content Safety."
        return state

    # ──────────────────────────────────────
    # PII Redaction
    # ──────────────────────────────────────
    content = redact_pii(content)

    # ──────────────────────────────────────
    # Final Response
    # ──────────────────────────────────────
    state["response"] = content

    state["policy_decisions"].append({
        "node": "llm_node",
        "rule": "FINAL_RESPONSE",
        "action": "allowed"
    })

    print(
        f"[LLM Node] Done | Model: {selected_model} | "
        f"Tokens: {tokens_used} | Latency: {latency_ms}ms | Cost: ${cost}"
    )

    return state