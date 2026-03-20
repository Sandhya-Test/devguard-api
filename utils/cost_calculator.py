# utils/cost_calculator.py
#
# Model-aware cost calculation.
# Prices are per 1,000 tokens (blended input+output approximation).
#
# Azure OpenAI pricing reference (as of 2025):
#   gpt-4o-mini : $0.00015 / 1K tokens
#   gpt-4o      : $0.005   / 1K tokens
 
COST_PER_1K_TOKENS = {
    "gpt-4o-mini": 0.00015,
    "gpt-4o":      0.005,
}
 
DEFAULT_RATE = 0.00015  # fallback if model not found
 
 
def calculate_cost(tokens: int, model: str = "gpt-4o-mini") -> float:
    """
    Returns the estimated cost in USD for the given token count and model.
 
    Args:
        tokens: Total tokens used (input + output)
        model:  Azure deployment name (e.g. 'gpt-4o-mini', 'gpt-4o')
 
    Returns:
        Cost in USD rounded to 6 decimal places
    """
    rate = COST_PER_1K_TOKENS.get(model, DEFAULT_RATE)
    return round((tokens / 1000) * rate, 6)