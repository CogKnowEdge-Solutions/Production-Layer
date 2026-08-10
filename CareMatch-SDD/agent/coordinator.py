"""The coordinator agent. It sits above the specialized subagents, decides which
one (or several) should handle a request, and synthesizes the final answer.

Tools available to the coordinator are the subagents themselves, so work is
distributed: the coordinator can fan out to auth, trials, eligibility,
assessments, caregivers, and audit agents as needed.
"""

from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import tool

from agent.session import AgentSession
from agent.subagents import build_subagents

COORDINATOR_PROMPT = (
    "You are the coordinator of the CareMatch clinical trial eligibility system. "
    "You have a team of specialized subagents below you. Delegate work to the "
    "appropriate subagent rather than answering directly, then synthesize their "
    "reports into a clear, concise answer for the user.\n\n"
    "Team:\n"
    "- auth_agent: login to CareMatch\n"
    "- trials_agent: create/list/get/update clinical trials\n"
    "- eligibility_agent: evaluate patient eligibility (FHIR) against a trial\n"
    "- assessments_agent: review, approve, or override AI recommendations\n"
    "- caregivers_agent: manage patient caregivers\n"
    "- audit_agent: audit trail and system metrics\n\n"
    "Guidelines:\n"
    "- If the user hasn't logged in yet and an authenticated action is needed, "
    "ask them for credentials and delegate to auth_agent.\n"
    "- The eligibility_agent returns an assessment_id; hand it to "
    "assessments_agent when the user wants to review/approve.\n"
    "- Always report the assessment_id, trial_id, and per-rule evidence that "
    "the subagents return.\n"
    "- Never invent data. If a tool errors, report the error to the user.\n"
    "- End with a short plain-language summary plus key IDs."
)


def build_coordinator(model: BaseChatModel, session: AgentSession) -> Any:
    subagents = build_subagents(model, session)
    run = subagents["run"]

    @tool("delegate_to_auth_agent")
    def delegate_auth(query: str) -> str:
        """Handle authentication (logging in). query is the user's request/credentials."""
        return run("auth", query)

    @tool("delegate_to_trials_agent")
    def delegate_trials(query: str) -> str:
        """Manage clinical trials: list, get, create, update."""
        return run("trials", query)

    @tool("delegate_to_eligibility_agent")
    def delegate_eligibility(query: str) -> str:
        """Evaluate a patient's eligibility for a trial (takes FHIR data)."""
        return run("eligibility", query)

    @tool("delegate_to_assessments_agent")
    def delegate_assessments(query: str) -> str:
        """Review, approve, or override eligibility assessment recommendations."""
        return run("assessments", query)

    @tool("delegate_to_caregivers_agent")
    def delegate_caregivers(query: str) -> str:
        """Manage patient caregivers: list or register."""
        return run("caregivers", query)

    @tool("delegate_to_audit_agent")
    def delegate_audit(query: str) -> str:
        """Fetch audit trail or system metrics."""
        return run("audit", query)

    coordinator_tools = [
        delegate_auth,
        delegate_trials,
        delegate_eligibility,
        delegate_assessments,
        delegate_caregivers,
        delegate_audit,
    ]
    return create_agent(
        model, tools=coordinator_tools, system_prompt=COORDINATOR_PROMPT, name="coordinator"
    )
