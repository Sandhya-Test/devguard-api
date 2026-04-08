import os

import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

CONTENT_SAFETY_ENDPOINT = (os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT") or "").strip().rstrip("/")
CONTENT_SAFETY_KEY = os.getenv("AZURE_CONTENT_SAFETY_KEY")
CONTENT_SAFETY_FAIL_OPEN = os.getenv("CONTENT_SAFETY_FAIL_OPEN", "false").lower() == "true"

CONTENT_SAFETY_TIMEOUT = 5
BLOCK_SEVERITY = 4


def _fallback_result() -> bool:
    return True if CONTENT_SAFETY_FAIL_OPEN else False


async def check_content_safety(text: str) -> bool:
    if not CONTENT_SAFETY_ENDPOINT or not CONTENT_SAFETY_KEY:
        print("[Content Safety] Credentials not set.")
        return _fallback_result()

    url = f"{CONTENT_SAFETY_ENDPOINT}/contentsafety/text:analyze?api-version=2023-10-01"
    payload = {
        "text": text[:1000],
        "categories": ["Hate", "SelfHarm", "Sexual", "Violence"],
        "outputType": "FourSeverityLevels",
    }
    headers = {
        "Ocp-Apim-Subscription-Key": CONTENT_SAFETY_KEY,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=CONTENT_SAFETY_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            print(f"[Content Safety] API error {response.status_code}.")
            return _fallback_result()

        result = response.json()
        for category in result.get("categoriesAnalysis", []):
            if category.get("severity", 0) >= BLOCK_SEVERITY:
                print(
                    f"[Content Safety] Blocked: {category['category']} "
                    f"severity {category['severity']}"
                )
                return False

        return True
    except httpx.TimeoutException:
        print("[Content Safety] Timeout.")
        return _fallback_result()
    except Exception as error:
        print(f"[Content Safety] Error: {error}")
        return _fallback_result()
