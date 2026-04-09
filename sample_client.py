import os

import requests
from dotenv import load_dotenv

load_dotenv()

api_base_url = (os.getenv("DEVGUARD_API_BASE_URL") or "http://localhost:8000").rstrip("/")
url = f"{api_base_url}/generate"

data = {
    "project_id": "external_app",
    "prompt": "Explain artificial intelligence"
}

response = requests.post(url, json=data)

print("Status:", response.status_code)
print("Response:", response.json())
