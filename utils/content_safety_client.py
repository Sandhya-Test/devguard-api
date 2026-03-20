import os
from azure.ai.contentsafety import ContentSafetyClient
from azure.core.credentials import AzureKeyCredential

endpoint = os.getenv("CONTENT_SAFETY_ENDPOINT")
key = os.getenv("CONTENT_SAFETY_KEY")

content_client = ContentSafetyClient(
    endpoint,
    AzureKeyCredential(key)
)