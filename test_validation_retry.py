import asyncio
import importlib


builder_module = importlib.import_module("graph.builder")
llm_module = importlib.import_module("graph.nodes.llm_node")
validation_module = importlib.import_module("graph.nodes.validation_node")


def test_validation_requests_retry_on_first_grounding_failure(monkeypatch):
    async def fake_assess_response(prompt, response):
        return {
            "passed": True,
            "action": "allowed",
            "reason": "Response passed lightweight hallucination screening.",
        }

    async def fake_check_source_grounding(prompt, response, context_chunks):
        return {
            "grounded": False,
            "confidence": "LOW",
            "reason": "Response has limited overlap with the provided context.",
        }

    monkeypatch.setattr(validation_module, "assess_response", fake_assess_response)
    monkeypatch.setattr(validation_module, "check_source_grounding", fake_check_source_grounding)

    state = {
        "request_id": "DG-val-1",
        "prompt": "What is the capital of France?",
        "response": "Berlin is the capital of France.",
        "project_id": "project_alpha",
        "context_chunks": ["Paris is the capital of France."],
        "allowed": True,
        "violations": [],
        "policy_decisions": [],
        "validation_retry_count": 0,
        "max_validation_retries": 1,
        "validation_retry_requested": False,
        "validation_retry_reason": None,
    }

    result = asyncio.run(validation_module.validation_node(state))

    assert result["allowed"] is True
    assert result["validation_retry_requested"] is True
    assert result["validation_retry_count"] == 1
    assert result["validation_retry_reason"]
    assert result["violations"] == []
    assert result["policy_decisions"][-1]["action"] == "retry_requested"


def test_validation_blocks_after_retry_limit(monkeypatch):
    async def fake_assess_response(prompt, response):
        return {
            "passed": True,
            "action": "allowed",
            "reason": "Response passed lightweight hallucination screening.",
        }

    async def fake_check_source_grounding(prompt, response, context_chunks):
        return {
            "grounded": False,
            "confidence": "LOW",
            "reason": "Response has limited overlap with the provided context.",
        }

    monkeypatch.setattr(validation_module, "assess_response", fake_assess_response)
    monkeypatch.setattr(validation_module, "check_source_grounding", fake_check_source_grounding)

    state = {
        "request_id": "DG-val-2",
        "prompt": "What is the capital of France?",
        "response": "Berlin is the capital of France.",
        "project_id": "project_alpha",
        "context_chunks": ["Paris is the capital of France."],
        "allowed": True,
        "violations": [],
        "policy_decisions": [],
        "validation_retry_count": 1,
        "max_validation_retries": 1,
        "validation_retry_requested": False,
        "validation_retry_reason": "Response has limited overlap with the provided context.",
    }

    result = asyncio.run(validation_module.validation_node(state))

    assert result["allowed"] is False
    assert result["validation_retry_requested"] is False
    assert "LOW_CONFIDENCE_RESPONSE" in result["violations"]
    assert "HALLUCINATION_RISK" in result["violations"]
    assert "Response blocked by validation policy" in result["response"]
    assert result["policy_decisions"][-1]["action"] == "ended_after_retry_limit"


def test_route_after_validation_goes_back_to_governance_for_retry():
    route = builder_module.route_after_validation(
        {"allowed": True, "validation_retry_requested": True}
    )
    assert route == "governance"


def test_llm_retry_prompt_includes_validation_feedback(monkeypatch):
    captured = {}

    async def fake_call_llm(prompt, model=None, max_tokens=None):
        captured["prompt"] = prompt
        captured["model"] = model
        captured["max_tokens"] = max_tokens
        return "Paris is the capital of France.", 50

    class FakeTokenStore:
        async def update_tokens(self, project_id, tokens_used, budget_date=None):
            return {
                "tokens_used_request": tokens_used,
                "tokens_used_total": tokens_used,
                "tokens_remaining": 99950,
                "token_quota": 100000,
                "quota_date": budget_date or "2026-04-08",
                "approved_quota_increase": 0,
            }

    async def fake_check_content_safety(text):
        return True

    monkeypatch.setattr(llm_module, "select_model", lambda prompt: "gpt-4o-mini")
    monkeypatch.setattr(llm_module, "call_llm", fake_call_llm)
    monkeypatch.setattr(llm_module, "TokenStore", FakeTokenStore)
    monkeypatch.setattr(llm_module, "check_content_safety", fake_check_content_safety)
    monkeypatch.setattr(llm_module, "calculate_cost", lambda tokens, model=None: 0.0)

    state = {
        "request_id": "DG-val-3",
        "prompt": "What is the capital of France?",
        "response": "Berlin is the capital of France.",
        "project_id": "project_alpha",
        "context_chunks": ["Paris is the capital of France."],
        "allowed": True,
        "violations": [],
        "policy_decisions": [],
        "validation_retry_count": 1,
        "max_validation_retries": 1,
        "validation_retry_requested": True,
        "validation_retry_reason": "Response has limited overlap with the provided context.",
        "max_output_tokens": 128,
        "quota_date": "2026-04-08",
    }

    result = asyncio.run(llm_module.llm_node(state))

    assert result["allowed"] is True
    assert result["validation_retry_requested"] is False
    assert "Validation Feedback:" in captured["prompt"]
    assert "Previous Answer:" in captured["prompt"]
    assert captured["max_tokens"] == 128
