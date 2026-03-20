# policies/pii_detector.py
 
import re
 
# ---------------------------------------------------
# Email Pattern
# ---------------------------------------------------
EMAIL_PATTERN = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
 
# ---------------------------------------------------
# Phone Pattern
# Matches:
# 9876543210
# +1-234-567-8901
# (123) 456-7890
# 123-456-7890
# 123 456 7890
# ---------------------------------------------------
PHONE_PATTERN = r"""
\b(
    (\+?\d{1,3}[-.\s]?)?      # country code
    (\(?\d{3}\)?[-.\s]?)      # area code
    \d{3}[-.\s]?\d{4}         # local number
)\b
"""
 
# ---------------------------------------------------
# Credit Card Pattern
# Matches:
# 1234567890123456
# 1234 5678 9012 3456
# 1234-5678-9012-3456
# ---------------------------------------------------
CREDIT_CARD_PATTERN = r"""
\b(
    (?:\d[ -]*?){13,16}
)\b
"""
 
 
def redact_pii(text: str) -> str:
 
    text = re.sub(EMAIL_PATTERN, "[REDACTED_EMAIL]", text)
 
    text = re.sub(
        PHONE_PATTERN,
        "[REDACTED_PHONE]",
        text,
        flags=re.VERBOSE
    )
 
    text = re.sub(
        CREDIT_CARD_PATTERN,
        "[REDACTED_CARD]",
        text,
        flags=re.VERBOSE
    )
 
    return text