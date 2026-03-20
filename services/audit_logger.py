# services/audit_logger.py

import os
import uuid
import asyncio
from datetime import datetime
from azure.cosmos import CosmosClient


class AuditLogger:

    def __init__(self):

        cosmos_uri = os.getenv("COSMOS_URI")
        cosmos_key = os.getenv("COSMOS_KEY")

        self.client = CosmosClient(cosmos_uri, credential=cosmos_key)

        self.database = self.client.get_database_client("devguard")

        self.container = self.database.get_container_client("audit_logs")

    async def log_request(self, state: dict):

        document = {
            "id": str(uuid.uuid4()),
            "project_id": state.get("project_id"),
            "request_id": state.get("request_id"),
            "prompt": state.get("prompt"),
            "response": state.get("response"),
            "allowed": state.get("allowed"),
            "violations": state.get("violations", []),
            "policy_decisions": state.get("policy_decisions", []),
            "latency_ms": state.get("latency_ms"),
            "tokens_used_request": state.get("tokens_used_request"),
            "tokens_used_total": state.get("tokens_used_total"),
            "cost_usd": state.get("cost_usd"),
            "model_used": state.get("model_used"),
            "timestamp": datetime.utcnow().isoformat()
        }

        retries = 3

        for attempt in range(retries):

            try:

                self.container.create_item(body=document)

                print("[Audit Logger] Log stored.")
                return

            except Exception as e:

                print(f"[Audit Logger] Write failed attempt {attempt+1}:", str(e))

                await asyncio.sleep(1)

        print("[Audit Logger] Failed after retries.")