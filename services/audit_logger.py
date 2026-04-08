import asyncio
import os
import uuid
from datetime import datetime

from azure.cosmos.aio import CosmosClient
from dotenv import load_dotenv

load_dotenv(override=True)


class AuditLogger:
    def __init__(self):
        cosmos_uri = os.getenv("COSMOS_URI")
        cosmos_key = os.getenv("COSMOS_KEY")
        cosmos_database = os.getenv("COSMOS_DATABASE", "devguard")
        cosmos_container = os.getenv("COSMOS_CONTAINER", "audit_logs")

        self.client = CosmosClient(cosmos_uri, credential=cosmos_key)
        self.database = self.client.get_database_client(cosmos_database)
        self.container = self.database.get_container_client(cosmos_container)

    async def log_request(self, state: dict):
        document = {
            "id": str(uuid.uuid4()),
            "project_id": state.get("project_id"),
            "request_id": state.get("request_id"),
            "quota_period": state.get("quota_period"),
            "quota_window_key": state.get("quota_window_key"),
            "quota_window_start": state.get("quota_window_start"),
            "quota_window_end": state.get("quota_window_end"),
            "quota_date": state.get("quota_date"),
            "prompt": state.get("prompt"),
            "context_chunks": state.get("context_chunks", []),
            "response": state.get("response"),
            "allowed": state.get("allowed"),
            "violations": state.get("violations", []),
            "policy_decisions": state.get("policy_decisions", []),
            "validation_retry_count": state.get("validation_retry_count"),
            "max_validation_retries": state.get("max_validation_retries"),
            "validation_retry_reason": state.get("validation_retry_reason"),
            "estimated_tokens": state.get("estimated_tokens"),
            "estimated_input_tokens": state.get("estimated_input_tokens"),
            "max_output_tokens": state.get("max_output_tokens"),
            "latency_ms": state.get("latency_ms"),
            "tokens_used_request": state.get("tokens_used_request"),
            "tokens_used_total": state.get("tokens_used_total"),
            "tokens_remaining": state.get("tokens_remaining"),
            "token_quota": state.get("token_quota"),
            "approved_quota_increase": state.get("approved_quota_increase"),
            "cost_usd": state.get("cost_usd"),
            "model_used": state.get("model_used"),
            "grounding_result": state.get("grounding_result"),
            "validation_summary": state.get("validation_summary"),
            "logic_trace": state.get("logic_trace"),
            "reasoning_score": state.get("reasoning_score"),
            "timestamp": datetime.utcnow().isoformat(),
        }

        retries = 3
        try:
            for attempt in range(retries):
                try:
                    await self.container.create_item(body=document)
                    print("[Audit Logger] Log stored.")
                    return
                except Exception as error:
                    print(f"[Audit Logger] Write failed attempt {attempt + 1}: {error}")
                    await asyncio.sleep(1)

            print("[Audit Logger] Failed after retries.")
        finally:
            await self.client.close()
