"""Live smoke test for the CareMatch agent team.

Runs the real coordinator against the real API and OpenRouter model.
Requires:
  - the API running on http://localhost:8000
  - OPENROUTER_API_KEY set in .env

Usage:
    python3 agent/smoke_test.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.config import get_agent_settings
from agent.coordinator import build_coordinator
from agent.model import build_model
from agent.session import AgentSession


def run(message: str) -> str:
    settings = get_agent_settings()
    session = AgentSession(base_url=settings.agent_api_url)
    model = build_model(settings.openrouter_model, settings.openrouter_api_key)
    coordinator = build_coordinator(model, session)
    result = coordinator.invoke({"messages": [{"role": "user", "content": message}]})
    messages = result.get("messages", [])
    return str(messages[-1].content) if messages else "No response."


if __name__ == "__main__":
    settings = get_agent_settings()
    if not settings.openrouter_api_key:
        sys.exit("OPENROUTER_API_KEY not set in .env")

    cases = [
        "Log in as admin / admin-password-change-me, then list trials and summarize.",
        (
            "Log in as admin / admin-password-change-me. Create a trial named 'Agent Smoke Trial' "
            'with protocol: "Inclusion criteria: Patient must be at least 18 years old. '
            'Patient has diabetes." Then evaluate a 45-year-old patient with diabetes '
            "against it and report the assessment_id and overall status."
        ),
    ]
    for case in cases:
        print("=" * 70)
        print("QUERY:", case)
        print("-" * 70)
        try:
            print(run(case))
        except Exception as exc:  # pragma: no cover - smoke only
            print(f"SMOKE FAILURE: {exc}")
    print("=" * 70)
    print("Smoke test complete.")
