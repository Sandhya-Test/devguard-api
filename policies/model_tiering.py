# policies/model_tiering.py
#
# Complexity Scorer — routes simple prompts to cheaper models,
# complex prompts to more capable (expensive) models.
#
# Tiers:
#   SIMPLE  → gpt-4o-mini  (cheap, fast)
#   COMPLEX → gpt-4o       (capable, expensive)
 
import os
from dotenv import load_dotenv
 
load_dotenv()
 
# ── Model names pulled from .env ──
# Same endpoint and key for both — only deployment name differs
SIMPLE_MODEL  = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
COMPLEX_MODEL = os.getenv("AZURE_OPENAI_DEPLOYMENT_COMPLEX", "gpt-4o")
 
# ── Keywords that indicate a SIMPLE prompt ──
SIMPLE_KEYWORDS = [
    "what is", "define", "translate", "spell", "convert",
    "list", "name", "when was", "who is", "how many",
    "yes or no", "true or false", "summarize in one",
    "give me a word", "simple", "briefly", "short answer",
]
 
# ── Keywords that indicate a COMPLEX prompt ──
COMPLEX_KEYWORDS = [
    "analyze", "compare", "explain in detail", "write a full",
    "design", "architect", "plan", "strategy", "evaluate",
    "pros and cons", "step by step", "in depth", "research",
    "generate code", "debug", "refactor", "reason",
]
 
SIMPLE_TOKEN_THRESHOLD  = 30    # very short prompts → likely simple
COMPLEX_TOKEN_THRESHOLD = 200   # very long prompts  → likely complex
 
 
def score_complexity(prompt: str) -> str:
    """
    Returns 'simple' or 'complex' based on prompt content and length.
    """
    prompt_lower = prompt.lower()
    word_count   = len(prompt.split())
 
    # Very long prompt → always complex
    if word_count >= COMPLEX_TOKEN_THRESHOLD:
        return "complex"
 
    # Check complex keywords first (higher priority)
    for kw in COMPLEX_KEYWORDS:
        if kw in prompt_lower:
            return "complex"
 
    # Short prompt + simple keyword → simple
    if word_count <= SIMPLE_TOKEN_THRESHOLD:
        for kw in SIMPLE_KEYWORDS:
            if kw in prompt_lower:
                return "simple"
 
    # Default → simple (always prefer cheaper model when unsure)
    return "simple"
 
 
def select_model(prompt: str) -> str:
    """
    Returns the Azure deployment name to use based on prompt complexity.
 
    Simple  → AZURE_OPENAI_DEPLOYMENT         (gpt-4o-mini)
    Complex → AZURE_OPENAI_DEPLOYMENT_COMPLEX  (gpt-4o)
 
    Both use the same endpoint and API key from .env —
    only the deployment name is different.
    """
    complexity = score_complexity(prompt)
 
    model_map = {
        "simple":  SIMPLE_MODEL,
        "complex": COMPLEX_MODEL,
    }
 
    selected = model_map[complexity]
 
    print(f"[Model Tiering] Word count: {len(prompt.split())} | Complexity: {complexity} → Model: {selected}")
 
    return selected