def _tokenize(text: str) -> set[str]:
    tokens = set()
    for token in text.split():
        cleaned = token.strip(".,!?;:()[]{}\"'").lower()
        if cleaned and len(cleaned) > 2:
            tokens.add(cleaned)
    return tokens


async def check_source_grounding(prompt: str, response: str, context_chunks: list) -> dict:
    if not context_chunks:
        return {
            "grounded": True,
            "confidence": "HIGH",
            "reason": "No context chunks provided - grounding check skipped.",
        }

    response_tokens = _tokenize(response)
    context_tokens = set()
    for chunk in context_chunks:
        context_tokens.update(_tokenize(chunk))

    if not response_tokens:
        return {
            "grounded": False,
            "confidence": "LOW",
            "reason": "Response was empty after validation.",
        }

    shared_tokens = response_tokens.intersection(context_tokens)
    overlap_ratio = len(shared_tokens) / len(response_tokens)

    if overlap_ratio >= 0.35:
        confidence = "HIGH"
        grounded = True
        reason = "Response substantially overlaps with the provided context."
    elif overlap_ratio >= 0.15:
        confidence = "MEDIUM"
        grounded = True
        reason = "Response partially overlaps with the provided context."
    else:
        confidence = "LOW"
        grounded = False
        reason = "Response has limited overlap with the provided context."

    return {
        "grounded": grounded,
        "confidence": confidence,
        "reason": reason,
    }
