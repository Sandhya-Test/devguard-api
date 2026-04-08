import os
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from azure.cosmos.aio import CosmosClient
from dotenv import load_dotenv

load_dotenv(override=True)

COSMOS_URI = os.getenv("COSMOS_URI")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DATABASE_NAME = os.getenv("COSMOS_DATABASE", "devguard")
CONTAINER_NAME = os.getenv("COSMOS_TOKEN_CONTAINER", "token_usage")

SUPPORTED_QUOTA_PERIODS = {"daily", "weekly", "monthly", "yearly"}
DEFAULT_MAX_TOKENS = int(
    os.getenv("DEFAULT_TOKEN_QUOTA", os.getenv("DEFAULT_DAILY_TOKEN_QUOTA", "100000"))
)


def _normalize_quota_period(value: Optional[str]) -> str:
    normalized = (value or "daily").strip().lower()
    if normalized not in SUPPORTED_QUOTA_PERIODS:
        raise ValueError(
            "TOKEN_QUOTA_PERIOD must be one of: daily, weekly, monthly, yearly."
        )
    return normalized


TOKEN_QUOTA_PERIOD = _normalize_quota_period(os.getenv("TOKEN_QUOTA_PERIOD"))


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _parse_reference_date(reference_date: Optional[str]) -> date:
    if not reference_date:
        return _utc_today()
    return date.fromisoformat(reference_date)


def _resolve_quota_window(reference_date: Optional[str] = None) -> dict[str, str]:
    reference = _parse_reference_date(reference_date)

    if TOKEN_QUOTA_PERIOD == "daily":
        start = reference
        end = reference
        key = start.isoformat()
    elif TOKEN_QUOTA_PERIOD == "weekly":
        start = reference - timedelta(days=reference.weekday())
        end = start + timedelta(days=6)
        iso_year, iso_week, _ = start.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
    elif TOKEN_QUOTA_PERIOD == "monthly":
        start = reference.replace(day=1)
        end = reference.replace(day=monthrange(reference.year, reference.month)[1])
        key = f"{start.year}-{start.month:02d}"
    else:
        start = reference.replace(month=1, day=1)
        end = reference.replace(month=12, day=31)
        key = f"{start.year}"

    return {
        "period": TOKEN_QUOTA_PERIOD,
        "window_key": key,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
    }


def _record_id(project_id: str, window: dict[str, str]) -> str:
    return f"{project_id}:{window['period']}:{window['window_key']}"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class TokenStore:
    def __init__(self):
        if not COSMOS_URI:
            raise RuntimeError("COSMOS_URI not found")
        if not COSMOS_KEY:
            raise RuntimeError("COSMOS_KEY not found")

        print("[Cosmos] Connecting to database...")
        self.client = CosmosClient(COSMOS_URI, credential=COSMOS_KEY)
        self.database = self.client.get_database_client(DATABASE_NAME)
        self.container = self.database.get_container_client(CONTAINER_NAME)
        print("[Cosmos] Connected successfully.")

    async def _close(self):
        try:
            await self.client.close()
        except Exception:
            pass

    def _build_new_quota_record(self, project_id: str, window: dict[str, str]) -> dict[str, Any]:
        return {
            "id": _record_id(project_id, window),
            "project_id": project_id,
            "quota_period": window["period"],
            "quota_window_key": window["window_key"],
            "quota_window_start": window["window_start"],
            "quota_window_end": window["window_end"],
            # Backward-compatible alias retained for existing API consumers/tests.
            "budget_date": window["window_start"],
            "tokens_used": 0,
            "base_token_quota": DEFAULT_MAX_TOKENS,
            "approved_quota_increase": 0,
            "token_quota": DEFAULT_MAX_TOKENS,
            "last_quota_approved_by": None,
            "last_quota_approved_at": None,
        }

    def _quota_snapshot(self, item: dict[str, Any]) -> dict[str, Any]:
        tokens_used = _safe_int(item.get("tokens_used"))
        quota = _safe_int(item.get("token_quota"), DEFAULT_MAX_TOKENS)
        quota_period = item.get("quota_period") or TOKEN_QUOTA_PERIOD
        quota_window_start = item.get("quota_window_start") or item.get("budget_date")
        quota_window_end = item.get("quota_window_end") or quota_window_start
        quota_window_key = item.get("quota_window_key") or quota_window_start

        return {
            "tokens_used_total": tokens_used,
            "tokens_remaining": quota - tokens_used,
            "token_quota": quota,
            "quota_period": quota_period,
            "quota_window_key": quota_window_key,
            "quota_window_start": quota_window_start,
            "quota_window_end": quota_window_end,
            "quota_date": quota_window_start,
            "approved_quota_increase": _safe_int(item.get("approved_quota_increase")),
        }

    async def get_or_create_project(
        self,
        project_id: str,
        budget_date: Optional[str] = None,
    ):
        window = _resolve_quota_window(budget_date)
        record_id = _record_id(project_id, window)

        try:
            item = await self.container.read_item(
                item=record_id,
                partition_key=project_id,
            )
            return item

        except Exception:
            print(f"[Cosmos] Creating {window['period']} quota record: {record_id}")
            new_item = self._build_new_quota_record(project_id, window)
            await self.container.create_item(body=new_item)
            return new_item

    async def check_quota(
        self,
        project_id: str,
        estimated_tokens: int,
        budget_date: Optional[str] = None,
    ):
        try:
            item = await self.get_or_create_project(project_id, budget_date)
            snapshot = self._quota_snapshot(item)

            print(
                "[Token Store] Quota usage | "
                f"Period: {snapshot['quota_period']} | "
                f"Window: {snapshot['quota_window_start']} -> {snapshot['quota_window_end']} | "
                f"Used: {snapshot['tokens_used_total']} | "
                f"Remaining: {snapshot['tokens_remaining']}"
            )

            if snapshot["tokens_remaining"] <= 0:
                return {"allowed": False, **snapshot}

            if estimated_tokens > snapshot["tokens_remaining"]:
                print("[Token Store] Predicted quota breach for current period - blocking")
                return {"allowed": False, **snapshot}

            return {"allowed": True, **snapshot}

        finally:
            await self._close()

    async def update_tokens(
        self,
        project_id: str,
        tokens_used_request: int,
        budget_date: Optional[str] = None,
    ):
        try:
            item = await self.get_or_create_project(project_id, budget_date)
            item["tokens_used"] = _safe_int(item.get("tokens_used")) + int(tokens_used_request)

            await self.container.replace_item(item=item, body=item)

            snapshot = self._quota_snapshot(item)
            print(
                "[Token Store] Updated quota usage | "
                f"Period: {snapshot['quota_period']} | "
                f"Window: {snapshot['quota_window_start']} -> {snapshot['quota_window_end']} | "
                f"Used: {snapshot['tokens_used_total']} | "
                f"Remaining: {snapshot['tokens_remaining']}"
            )

            return {
                "tokens_used_request": tokens_used_request,
                **snapshot,
            }

        finally:
            await self._close()

    async def approve_quota_increase(
        self,
        project_id: str,
        additional_tokens: int,
        approved_by: str,
        budget_date: Optional[str] = None,
    ):
        if additional_tokens <= 0:
            raise ValueError("additional_tokens must be greater than 0.")
        if not approved_by.strip():
            raise ValueError("approved_by is required.")

        try:
            item = await self.get_or_create_project(project_id, budget_date)
            approved_total = _safe_int(item.get("approved_quota_increase")) + int(additional_tokens)
            approved_at = datetime.now(timezone.utc).isoformat()

            item["approved_quota_increase"] = approved_total
            item["token_quota"] = _safe_int(item.get("base_token_quota"), DEFAULT_MAX_TOKENS) + approved_total
            item["last_quota_approved_by"] = approved_by.strip()
            item["last_quota_approved_at"] = approved_at

            await self.container.replace_item(item=item, body=item)

            snapshot = self._quota_snapshot(item)
            print(
                "[Token Store] Quota increase approved | "
                f"Period: {snapshot['quota_period']} | "
                f"Window: {snapshot['quota_window_start']} -> {snapshot['quota_window_end']} | "
                f"Project: {project_id} | "
                f"New quota: {snapshot['token_quota']}"
            )

            return {
                "project_id": project_id,
                "quota_period": snapshot["quota_period"],
                "quota_window_key": snapshot["quota_window_key"],
                "quota_window_start": snapshot["quota_window_start"],
                "quota_window_end": snapshot["quota_window_end"],
                "quota_date": snapshot["quota_date"],
                "token_quota": snapshot["token_quota"],
                "tokens_used_total": snapshot["tokens_used_total"],
                "tokens_remaining": snapshot["tokens_remaining"],
                "approved_quota_increase": snapshot["approved_quota_increase"],
                "approved_by": item["last_quota_approved_by"],
                "approved_at": item["last_quota_approved_at"],
            }

        finally:
            await self._close()
