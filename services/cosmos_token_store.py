# services/cosmos_token_store.py

import os
from azure.cosmos.aio import CosmosClient
from dotenv import load_dotenv

load_dotenv()

COSMOS_URI     = os.getenv("COSMOS_URI")
COSMOS_KEY     = os.getenv("COSMOS_KEY")
DATABASE_NAME  = "devguard"
CONTAINER_NAME = "token_usage"

# Default production quota
DEFAULT_MAX_TOKENS = 100000


class TokenStore:

    def __init__(self):
        if not COSMOS_URI:
            raise RuntimeError("COSMOS_URI not found")
        if not COSMOS_KEY:
            raise RuntimeError("COSMOS_KEY not found")

        print("[Cosmos] Connecting to database...")
        self.client    = CosmosClient(COSMOS_URI, credential=COSMOS_KEY)
        self.database  = self.client.get_database_client(DATABASE_NAME)
        self.container = self.database.get_container_client(CONTAINER_NAME)
        print("[Cosmos] Connected successfully.")

    async def _close(self):
        try:
            await self.client.close()
        except Exception:
            pass

    # ─────────────────────────────
    # Get / Create Project
    # ─────────────────────────────
    async def get_or_create_project(self, project_id: str):
        try:
            item = await self.container.read_item(
                item=project_id,
                partition_key=project_id
            )
            return item

        except Exception:
            print(f"[Cosmos] Creating new project: {project_id}")

            new_item = {
                "id": project_id,
                "project_id": project_id,
                "tokens_used": 0,
                "token_quota": DEFAULT_MAX_TOKENS
            }

            await self.container.create_item(body=new_item)
            return new_item

    # ─────────────────────────────
    # SMART QUOTA CHECK (UPDATED)
    # ─────────────────────────────
    async def check_quota(self, project_id: str, estimated_tokens: int):

        try:
            item = await self.get_or_create_project(project_id)

            tokens_used = item["tokens_used"]
            quota       = item["token_quota"]
            remaining   = quota - tokens_used

            print(f"[Token Store] Used: {tokens_used} | Remaining: {remaining}")

            # ❌ HARD BLOCK (no tokens)
            if remaining <= 0:
                return {
                    "allowed": False,
                    "tokens_used_total": tokens_used,
                    "tokens_remaining": remaining,
                    "token_quota": quota
                }

            # 🧠 PREDICTIVE BLOCK
            if estimated_tokens > remaining:
                print("[Token Store] Predicted quota breach — blocking")

                return {
                    "allowed": False,
                    "tokens_used_total": tokens_used,
                    "tokens_remaining": remaining,
                    "token_quota": quota
                }

            # ✅ ALLOW
            return {
                "allowed": True,
                "tokens_used_total": tokens_used,
                "tokens_remaining": remaining,
                "token_quota": quota
            }

        finally:
            await self._close()

    # ─────────────────────────────
    # UPDATE TOKENS (POST)
    # ─────────────────────────────
    async def update_tokens(self, project_id: str, tokens_used_request: int):

        try:
            item = await self.get_or_create_project(project_id)

            new_total = item["tokens_used"] + tokens_used_request
            quota     = item["token_quota"]

            item["tokens_used"] = new_total

            await self.container.replace_item(item=item, body=item)

            remaining = quota - new_total

            print(f"[Token Store] Updated — Used: {new_total} | Remaining: {remaining}")

            return {
                "tokens_used_request": tokens_used_request,
                "tokens_used_total": new_total,
                "tokens_remaining": remaining,
                "token_quota": quota
            }

        finally:
            await self._close()