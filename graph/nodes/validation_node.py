from policies.hallucination_checker import assess_response
from policies.pii_redactor import redact_pii
from policies.source_grounding import check_source_grounding

VALIDATION_BLOCK_MESSAGE = (
    "Response blocked by validation policy due to hallucination or grounding failure."
)


def _tokenize(text: str) -> set[str]:
    tokens = set()
    for token in text.split():
        cleaned = token.strip(".,!?;:()[]{}\"'").lower()
        if cleaned:
            tokens.add(cleaned)
    return tokens


def _estimate_context_overlap(response: str, context_chunks: list[str]) -> float:
    response_tokens = _tokenize(response)
    context_tokens = set()

    for chunk in context_chunks:
        context_tokens.update(_tokenize(chunk))

    if not response_tokens or not context_tokens:
        return 0.0

    return len(response_tokens.intersection(context_tokens)) / len(response_tokens)


def _append_violation(state: dict, violation: str) -> None:
    if violation not in state["violations"]:
        state["violations"].append(violation)


def _retry_summary_note(retry_count: int, max_retries: int) -> str:
    return f"Retrying response generation ({retry_count}/{max_retries})."


async def validation_node(state: dict):
    print("[Validation Node] Running response validation...")

    if not state.get("allowed", True):
        return state

    prompt = state.get("prompt", "")
    response = state.get("response", "")
    context_chunks = state.get("context_chunks", [])
    retry_count = int(state.get("validation_retry_count", 0))
    max_retries = int(state.get("max_validation_retries", 1))

    if not response:
        _append_violation(state, "EMPTY_RESPONSE")
        state["policy_decisions"].append(
            {"node": "validation_node", "rule": "VALIDATION", "action": "flagged_empty_response"}
        )
        state["validation_summary"] = {
            "response_length": 0,
            "context_overlap": 0.0,
            "notes": ["No response was available for validation."],
        }
        state["allowed"] = False
        state["validation_retry_requested"] = False
        state["validation_retry_reason"] = "No response was available for validation."
        state["response"] = VALIDATION_BLOCK_MESSAGE
        return state

    response = redact_pii(response)
    state["response"] = response

    response_word_count = len(response.split())
    notes: list[str] = []
    failure_reasons: list[str] = []

    hallucination_result = await assess_response(prompt, response)
    state["policy_decisions"].append(
        {
            "node": "validation_node",
            "rule": "HALLUCINATION_CHECK",
            "action": hallucination_result["action"],
        }
    )

    if not hallucination_result["passed"]:
        failure_reasons.append(hallucination_result["reason"])
        notes.append(hallucination_result["reason"])

    if not context_chunks:
        state["grounding_result"] = {
            "grounded": True,
            "confidence": "HIGH",
            "reason": "No context chunks provided - grounding check skipped.",
        }
        state["policy_decisions"].append(
            {"node": "validation_node", "rule": "SOURCE_GROUNDING", "action": "skipped_no_context"}
        )
        overlap_ratio = None
    else:
        print(f"[Validation Node] Running grounding check with {len(context_chunks)} chunks...")
        grounding = await check_source_grounding(prompt, response, context_chunks)
        state["grounding_result"] = grounding
        overlap_ratio = round(_estimate_context_overlap(response, context_chunks), 3)

        if not grounding["grounded"]:
            failure_reasons.append(grounding["reason"])
            notes.append(grounding["reason"])
            action = "low_confidence" if grounding["confidence"] == "LOW" else "ungrounded"
            state["policy_decisions"].append(
                {"node": "validation_node", "rule": "SOURCE_GROUNDING", "action": action}
            )
        else:
            state["policy_decisions"].append(
                {"node": "validation_node", "rule": "SOURCE_GROUNDING", "action": "allowed"}
            )

    if failure_reasons:
        retry_reason = " ".join(dict.fromkeys(failure_reasons))
        if retry_count < max_retries:
            next_retry_count = retry_count + 1
            state["validation_retry_count"] = next_retry_count
            state["validation_retry_requested"] = True
            state["validation_retry_reason"] = retry_reason
            state["policy_decisions"].append(
                {
                    "node": "validation_node",
                    "rule": "VALIDATION_RETRY",
                    "action": "retry_requested",
                    "attempt": next_retry_count,
                }
            )
            state["validation_summary"] = {
                "response_length": response_word_count,
                "context_overlap": overlap_ratio,
                "notes": notes + [_retry_summary_note(next_retry_count, max_retries)],
            }
            print(
                "[Validation Node] Validation failed - requesting retry | "
                f"Attempt {next_retry_count}/{max_retries}"
            )
            return state

        state["allowed"] = False
        _append_violation(state, "LOW_CONFIDENCE_RESPONSE")
        _append_violation(state, "HALLUCINATION_RISK")
        state["validation_retry_requested"] = False
        state["validation_retry_reason"] = retry_reason
        state["response"] = VALIDATION_BLOCK_MESSAGE
        state["policy_decisions"].append(
            {
                "node": "validation_node",
                "rule": "VALIDATION_RETRY",
                "action": "ended_after_retry_limit",
                "attempt": retry_count,
            }
        )
        state["validation_summary"] = {
            "response_length": response_word_count,
            "context_overlap": overlap_ratio,
            "notes": notes + ["Validation failed again after retry. Request ended."],
        }
        print("[Validation Node] Validation failed again - ending request.")
        return state

    state["validation_retry_requested"] = False
    state["validation_retry_reason"] = None
    state["validation_summary"] = {
        "response_length": response_word_count,
        "context_overlap": overlap_ratio,
        "notes": notes or ["Validation completed successfully."],
    }

    print("[Validation Node] Validation complete.")
    return state
