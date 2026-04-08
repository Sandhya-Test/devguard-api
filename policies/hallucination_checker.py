from typing import Any


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


async def assess_response(prompt: str, response: str) -> dict[str, Any]:
    """
    Lightweight response validation that avoids over-blocking while still
    catching clearly weak generations before we accept them.
    """
    if not prompt or not response:
        return {
            "passed": False,
            "action": "flagged_empty_response",
            "reason": "Prompt or response was empty during validation.",
        }

    normalized_prompt = _normalize(prompt)
    normalized_response = _normalize(response)

    if not normalized_response:
        return {
            "passed": False,
            "action": "flagged_empty_response",
            "reason": "Response was empty after normalization.",
        }

    prompt_word_count = len(normalized_prompt.split())
    response_word_count = len(normalized_response.split())
    low_information_responses = {"ok", "yes", "no", "maybe", "unknown", "n/a"}

    if response_word_count < 3 and prompt_word_count > 5:
        return {
            "passed": False,
            "action": "flagged_too_short",
            "reason": "Response is unusually short for the prompt complexity.",
        }

    if normalized_response in low_information_responses and prompt_word_count > 3:
        return {
            "passed": False,
            "action": "flagged_low_information",
            "reason": "Response is too low-information to trust for this prompt.",
        }

    return {
        "passed": True,
        "action": "allowed",
        "reason": "Response passed lightweight hallucination screening.",
    }


async def validate_response(prompt: str, response: str) -> bool:
    result = await assess_response(prompt, response)
    return result["passed"]
