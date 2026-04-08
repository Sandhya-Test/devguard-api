# services/content_safety.py
#
# Azure AI Content Safety API wrapper.
#
# FIX: Added explicit 5s timeout on the HTTP call so it never
# causes the LLM pipeline's asyncio.wait_for to time out.
# Used for BOTH input (prompt) and output (response) screening.
 
import os
import httpx
from dotenv import load_dotenv
 
load_dotenv()
 
CONTENT_SAFETY_ENDPOINT = os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT")
CONTENT_SAFETY_KEY      = os.getenv("AZURE_CONTENT_SAFETY_KEY")
 
CONTENT_SAFETY_TIMEOUT  = 5   # seconds — never let this block the pipeline
 
# Severity threshold — 0=safe, 2=low, 4=medium, 6=high
# Block anything medium or above
BLOCK_SEVERITY = 4
 
 
async def check_content_safety(text: str) -> bool:
    """
    Checks text against Azure Content Safety API.
 
    Returns:
        True  — content is safe, allow it
        False — content is unsafe, block it
 
    If the API is unreachable or times out, fails OPEN (returns True)
    so the pipeline is never blocked by a network issue.
    """
 
    if not CONTENT_SAFETY_ENDPOINT or not CONTENT_SAFETY_KEY:
        print("[Content Safety] Credentials not set — skipping check.")
        return True
 
    url = f"{CONTENT_SAFETY_ENDPOINT}/contentsafety/text:analyze?api-version=2023-10-01"
 
    payload = {
        "text": text[:1000],  # API limit
        "categories": ["Hate", "SelfHarm", "Sexual", "Violence"],
        "outputType": "FourSeverityLevels"
    }
 
    headers = {
        "Ocp-Apim-Subscription-Key": CONTENT_SAFETY_KEY,
        "Content-Type": "application/json"
    }
 
    try:
        async with httpx.AsyncClient(timeout=CONTENT_SAFETY_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
 
        if response.status_code != 200:
            print(f"[Content Safety] API error {response.status_code} — failing open.")
            return True
 
        result = response.json()
 
        for category in result.get("categoriesAnalysis", []):
            if category.get("severity", 0) >= BLOCK_SEVERITY:
                print(f"[Content Safety] Blocked: {category['category']} "
                      f"severity {category['severity']}")
                return False
 
        return True
 
    except httpx.TimeoutException:
        print("[Content Safety] Timeout — failing open.")
        return True
 
    except Exception as e:
        print(f"[Content Safety] Error — failing open: {e}")
        return True