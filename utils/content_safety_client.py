import os

from azure.ai.contentsafety import ContentSafetyClient
from azure.core.credentials import AzureKeyCredential

endpoint = (os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT") or "").strip().rstrip("/")
key = os.getenv("AZURE_CONTENT_SAFETY_KEY")

content_client = ContentSafetyClient(
    endpoint,
    AzureKeyCredential(key),
)
