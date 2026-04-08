# services/azure_openai.py
 
import os
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
import httpx
 
load_dotenv(override=True)
 
AZURE_ENDPOINT  = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_KEY       = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_VERSION   = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
 
http_client = httpx.AsyncClient(timeout=60.0)
 
client = AsyncAzureOpenAI(
    api_key=AZURE_KEY,
    azure_endpoint=AZURE_ENDPOINT,
    api_version=AZURE_VERSION,
    http_client=http_client,
)
 
 
async def call_llm(prompt: str, model: str = None, max_tokens: int | None = None):
    """
    Calls Azure OpenAI with the given prompt.
    If model is provided (from model tiering), uses that deployment.
    Falls back to AZURE_DEPLOYMENT env var.
    """
 
    deployment = model or AZURE_DEPLOYMENT
 
    request_args = {
        "model": deployment,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }
    if max_tokens is not None:
        request_args["max_tokens"] = max_tokens

    response = await client.chat.completions.create(**request_args)
 
    content     = response.choices[0].message.content
    tokens_used = response.usage.total_tokens
 
    return content, tokens_used
