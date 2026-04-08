import asyncio
import importlib

from fastapi.testclient import TestClient


governance_module = importlib.import_module("graph.nodes.governance_node")
api_main = importlib.import_module("api.main")


def _reload_token_store(monkeypatch, period: str):
    monkeypatch.setenv("TOKEN_QUOTA_PERIOD", period)
    monkeypatch.setenv("DEFAULT_TOKEN_QUOTA", "100000")
    module = importlib.import_module("services.cosmos_token_store")
    return importlib.reload(module)


def test_estimate_tokens_is_conservative_for_open_ended_prompt():
    estimated = governance_module.estimate_tokens("Explain transformers in deep learning")
    assert estimated > 100


def test_weekly_quota_window_resolution(monkeypatch):
    token_store_module = _reload_token_store(monkeypatch, "weekly")
    window = token_store_module._resolve_quota_window("2026-04-08")

    assert window["period"] == "weekly"
    assert window["window_key"] == "2026-W15"
    assert window["window_start"] == "2026-04-06"
    assert window["window_end"] == "2026-04-12"


def test_monthly_quota_window_resolution(monkeypatch):
    token_store_module = _reload_token_store(monkeypatch, "monthly")
    window = token_store_module._resolve_quota_window("2026-04-08")

    assert window["period"] == "monthly"
    assert window["window_key"] == "2026-04"
    assert window["window_start"] == "2026-04-01"
    assert window["window_end"] == "2026-04-30"


def test_yearly_quota_window_resolution(monkeypatch):
    token_store_module = _reload_token_store(monkeypatch, "yearly")
    window = token_store_module._resolve_quota_window("2026-04-08")

    assert window["period"] == "yearly"
    assert window["window_key"] == "2026"
    assert window["window_start"] == "2026-01-01"
    assert window["window_end"] == "2026-12-31"


def test_governance_blocks_when_estimate_exceeds_remaining_budget(monkeypatch):
    class FakeTokenStore:
        async def check_quota(self, project_id, estimated_tokens, budget_date=None):
            return {
                "allowed": False,
                "tokens_used_total": 100,
                "tokens_remaining": 0,
                "token_quota": 100,
                "quota_period": "daily",
                "quota_window_key": "2026-04-08",
                "quota_window_start": "2026-04-08",
                "quota_window_end": "2026-04-08",
                "quota_date": "2026-04-08",
                "approved_quota_increase": 0,
            }

    monkeypatch.setattr(governance_module, "TokenStore", FakeTokenStore)

    state = {
        "request_id": "DG-test-1",
        "prompt": "Explain transformers in deep learning",
        "project_id": "project_alpha",
        "context_chunks": [],
        "allowed": True,
        "violations": [],
        "policy_decisions": [],
    }

    result = asyncio.run(governance_module.governance_node(state))

    assert result["allowed"] is False
    assert "TOKEN_QUOTA_EXCEEDED" in result["violations"]
    assert result["policy_decisions"][-1]["action"] == "blocked"
    assert "quota exceeded" in result["response"].lower()


def test_quota_increase_endpoint_returns_updated_quota(monkeypatch):
    class FakeTokenStore:
        async def approve_quota_increase(self, project_id, additional_tokens, approved_by, budget_date=None):
            return {
                "project_id": project_id,
                "quota_period": "weekly",
                "quota_window_key": "2026-W15",
                "quota_window_start": "2026-04-06",
                "quota_window_end": "2026-04-12",
                "quota_date": "2026-04-06",
                "token_quota": 125000,
                "tokens_used_total": 100000,
                "tokens_remaining": 25000,
                "approved_quota_increase": 25000,
                "approved_by": approved_by,
                "approved_at": "2026-04-08T07:30:00+00:00",
            }

        async def check_quota(self, project_id, estimated_tokens, budget_date=None):
            return {
                "allowed": False,
                "tokens_used_total": 100000,
                "tokens_remaining": 0,
                "token_quota": 100000,
                "quota_period": "weekly",
                "quota_window_key": "2026-W15",
                "quota_window_start": "2026-04-06",
                "quota_window_end": "2026-04-12",
                "quota_date": "2026-04-06",
                "approved_quota_increase": 0,
            }

    monkeypatch.setattr(api_main, "TokenStore", FakeTokenStore)
    monkeypatch.setenv("MANAGER_APPROVAL_TOKEN", "manager-secret")

    client = TestClient(api_main.app)

    response = client.post(
        "/projects/project_alpha/quota/increase",
        headers={"x-manager-approval-token": "manager-secret"},
        json={
            "additional_tokens": 25000,
            "approved_by": "manager@example.com",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == "project_alpha"
    assert payload["quota_period"] == "weekly"
    assert payload["token_quota"] == 125000
    assert payload["approved_quota_increase"] == 25000


def test_quota_increase_endpoint_rejects_invalid_manager_token(monkeypatch):
    monkeypatch.setenv("MANAGER_APPROVAL_TOKEN", "manager-secret")
    client = TestClient(api_main.app)

    response = client.post(
        "/projects/project_alpha/quota/increase",
        headers={"x-manager-approval-token": "wrong-token"},
        json={
            "additional_tokens": 25000,
            "approved_by": "manager@example.com",
        },
    )

    assert response.status_code == 403


def test_get_quota_status_endpoint_uses_configured_period(monkeypatch):
    class FakeTokenStore:
        async def check_quota(self, project_id, estimated_tokens, budget_date=None):
            return {
                "allowed": True,
                "tokens_used_total": 42000,
                "tokens_remaining": 58000,
                "token_quota": 100000,
                "quota_period": "monthly",
                "quota_window_key": "2026-04",
                "quota_window_start": "2026-04-01",
                "quota_window_end": "2026-04-30",
                "quota_date": "2026-04-01",
                "approved_quota_increase": 0,
            }

    monkeypatch.setattr(api_main, "TokenStore", FakeTokenStore)

    client = TestClient(api_main.app)
    response = client.get("/projects/project_alpha/quota")

    assert response.status_code == 200
    payload = response.json()
    assert payload["allowed"] is True
    assert payload["quota_period"] == "monthly"
    assert payload["quota_window_start"] == "2026-04-01"
    assert payload["tokens_remaining"] == 58000
