"""Tests for the agent layer (coordinator, subagents, tools).

These tests verify the tool wiring and session/token propagation without
calling a real LLM or the real network: the CareMatch HTTP client's
`_request` method is stubbed, and tool inputs are invoked directly.

Note: the free OpenRouter tier is flaky by nature; the live agent smoke test
lives in agent/smoke_test.py and is run manually.
"""

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENV"] = "testing"
os.environ["JWT_SECRET"] = "test-secret-key-at-least-32-bytes-long!!"

import json

import pytest

from agent.session import AgentSession
from agent.tools import build_tools


def test_login_tool_stores_token():
    session = AgentSession(base_url="http://testserver")
    tools = {t.name: t for t in build_tools(session)}

    from agent.carematch_client import CareMatchClient

    original = CareMatchClient._request

    def fake_request(self, method, path, token=None, **kwargs):
        assert path == "/api/v1/auth/token"
        return {"access_token": "tok-123", "token_type": "bearer"}

    CareMatchClient._request = fake_request
    try:
        out = tools["login_to_carematch"].invoke(
            {"username": "admin", "password": "admin-password-change-me"}
        )
    finally:
        CareMatchClient._request = original

    assert "Login successful" in out
    assert session.token == "tok-123"


def test_tools_require_auth_then_use_token():
    session = AgentSession(base_url="http://testserver")
    tools = {t.name: t for t in build_tools(session)}

    from agent.carematch_client import CareMatchClient

    calls = []

    def fake_request(self, method, path, token=None, **kwargs):
        calls.append((method, path, token))
        if path == "/api/v1/auth/token":
            return {"access_token": "tok-abc"}
        if path == "/api/v1/trials":
            return {"items": [], "total": 0, "page": 1, "page_size": 50}
        raise AssertionError(f"unexpected path {path}")

    original = CareMatchClient._request
    CareMatchClient._request = fake_request
    try:
        tools["login_to_carematch"].invoke(
            {"username": "admin", "password": "admin-password-change-me"}
        )
        out = tools["list_trials"].invoke({"limit": 50})
    finally:
        CareMatchClient._request = original

    parsed = json.loads(out)
    assert parsed["total"] == 0
    assert calls[1] == ("GET", "/api/v1/trials", "tok-abc")


def test_override_rule_requires_reasoning():
    session = AgentSession(base_url="http://testserver")
    session.token = "tok"
    tools = {t.name: t for t in build_tools(session)}

    with pytest.raises(RuntimeError):
        tools["override_rule"].invoke(
            {
                "assessment_id": "a1",
                "rule_eval_id": "r1",
                "new_status": "DOES_NOT_MATCH",
                "reasoning": "no",
            }
        )


def test_create_trial_requires_name():
    session = AgentSession(base_url="http://testserver")
    session.token = "tok"
    tools = {t.name: t for t in build_tools(session)}

    with pytest.raises(RuntimeError):
        tools["create_trial"].invoke({"trial_name": "", "protocol_text": "- age 18"})


def test_agent_settings_defaults():
    from agent.config import AgentSettings

    settings = AgentSettings(_env_file=None)
    assert settings.agent_api_url == "http://localhost:8000"
    assert settings.openrouter_model
