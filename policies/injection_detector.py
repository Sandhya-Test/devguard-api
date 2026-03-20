# policies/injection_detector.py

import re

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"reveal\s+(your\s+)?system\s+prompt",
    r"reveal\s+hidden\s+instructions",
    r"bypass\s+safety",
    r"override\s+system",
    r"disregard\s+rules",
    r"act\s+as\s+developer",
    r"jailbreak",
]


def detect_injection(prompt: str) -> bool:
    prompt_lower = prompt.lower()

    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, prompt_lower):
            return True

    return False