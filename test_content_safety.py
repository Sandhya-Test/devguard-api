import os
import socket
from urllib.parse import urlparse

from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeTextOptions
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError, ServiceRequestError
from dotenv import load_dotenv

load_dotenv(override=True)


def _load_settings():
    endpoint = (os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT") or "").strip().rstrip("/")
    key = (os.getenv("AZURE_CONTENT_SAFETY_KEY") or "").strip()

    if not endpoint:
        raise RuntimeError("AZURE_CONTENT_SAFETY_ENDPOINT is not set.")
    if not key:
        raise RuntimeError("AZURE_CONTENT_SAFETY_KEY is not set.")

    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(
            "AZURE_CONTENT_SAFETY_ENDPOINT must look like "
            "https://<resource>.cognitiveservices.azure.com"
        )

    return endpoint, key, parsed.netloc


def main():
    endpoint, key, host = _load_settings()
    print(f"Connecting to Azure Content Safety at {host}...")

    try:
        socket.getaddrinfo(host, 443)
        print("DNS lookup succeeded.")
    except socket.gaierror as error:
        print(f"DNS lookup failed for {host}: {error}")
        print(
            "Check that AZURE_CONTENT_SAFETY_ENDPOINT exactly matches the "
            "resource endpoint shown in the Azure portal."
        )
        print(
            "If the endpoint is correct, verify this machine can resolve "
            "public Azure hostnames or reach the private endpoint DNS zone."
        )
        return

    client = ContentSafetyClient(endpoint, AzureKeyCredential(key))
    text_to_check = "I will destroy everything and hurt people."

    try:
        response = client.analyze_text(AnalyzeTextOptions(text=text_to_check))
    except ServiceRequestError as error:
        print(f"Request could not reach Azure: {error}")
        print(
            "This is usually a DNS, proxy, firewall, or private endpoint "
            "networking problem rather than a Python code issue."
        )
        return
    except HttpResponseError as error:
        print(f"Azure returned an API error: {error.message}")
        return
    except Exception as error:
        print(f"Unexpected error: {error}")
        return

    print("\nContent Safety response:\n")
    for category in response.categories_analysis:
        print(f"{category.category}: severity {category.severity}")


if __name__ == "__main__":
    main()
