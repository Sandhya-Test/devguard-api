import requests

url = "https://devguard-api.azurewebsites.net/generate"

data = {
    "project_id": "external_app",
    "prompt": "Explain artificial intelligence"
}

response = requests.post(url, json=data)

print("Status:", response.status_code)
print("Response:", response.json())