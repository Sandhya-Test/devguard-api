import asyncio
import os
import socket
from urllib.parse import urlparse

import pytest
from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, AsyncAzureOpenAI

load_dotenv(override=True)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is not set.")
    return value


def _load_settings():
    endpoint = _require_env("AZURE_OPENAI_ENDPOINT").strip().rstrip("/")
    api_key = _require_env("AZURE_OPENAI_API_KEY")
    api_version = _require_env("AZURE_OPENAI_API_VERSION")
    deployment = _require_env("AZURE_OPENAI_DEPLOYMENT")

    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(
            "AZURE_OPENAI_ENDPOINT must look like "
            "https://<resource>.openai.azure.com"
        )

    return endpoint, api_key, api_version, deployment, parsed.netloc


async def _run_live_check():
    endpoint, api_key, api_version, deployment, host = _load_settings()
    print(f"Connecting to Azure OpenAI at {host}...")

    try:
        socket.getaddrinfo(host, 443)
        print("DNS lookup succeeded.")
    except socket.gaierror as error:
        print(f"DNS lookup failed for {host}: {error}")
        print(
            "Check that AZURE_OPENAI_ENDPOINT exactly matches the "
            "resource endpoint shown in the Azure portal."
        )
        print(
            "If the endpoint is correct, verify this machine can resolve "
            "the Azure OpenAI hostname or reach the private endpoint DNS zone."
        )
        return

    client = AsyncAzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
    )

    try:
        response = await client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": "hello"}],
        )
    except APITimeoutError as error:
        print(f"Request timed out: {error}")
        print(
            "This is usually a DNS, proxy, firewall, or private endpoint "
            "networking problem rather than an LLM prompt issue."
        )
        return
    except APIConnectionError as error:
        print(f"Request could not reach Azure OpenAI: {error}")
        print(
            "This is usually a DNS, proxy, firewall, or private endpoint "
            "networking problem rather than an LLM prompt issue."
        )
        return

    content = response.choices[0].message.content
    assert content
    print("Azure OpenAI is working.")
    print(content)


def test_azure_live_connection():
    if os.getenv("RUN_LIVE_AZURE_TESTS", "false").lower() != "true":
        pytest.skip("Set RUN_LIVE_AZURE_TESTS=true to run the live Azure check.")

    asyncio.run(_run_live_check())


if __name__ == "__main__":
    asyncio.run(_run_live_check())
