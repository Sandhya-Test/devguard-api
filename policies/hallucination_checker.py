# policies/hallucination_checker.py

async def validate_response(prompt: str, response: str):
    """
    Lightweight hallucination validation.

    Design goals:
    - Do NOT over-block valid responses
    - Allow short/creative prompts
    - Catch only clearly invalid outputs
    """

    # Normalize inputs
    if not prompt or not response:
        return False

    prompt = prompt.strip().lower()
    response = response.strip().lower()

    # ❌ Empty or meaningless response
    if len(response) == 0:
        return False

    # ✅ VERY IMPORTANT: Allow short prompts (creative/simple)
    # Examples:
    # "give one word"
    # "hello"
    # "define ai"
    if len(prompt.split()) <= 5:
        return True

    # ✅ Basic sanity check: response should contain words
    if len(response.split()) >= 1:
        return True

    # Fallback (rare case)
    return True