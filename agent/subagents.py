"""Specialized subagents. Each has a focused system prompt and its own tool
subset, so work is distributed: a single request can fan out to several agents.
"""

from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel

from agent.session import AgentSession
from agent.tools import build_tools


def _final_answer(agent: Any, query: str) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": query}]})
    messages = result.get("messages", [])
    return messages[-1].content if messages else "No response from agent."


def build_subagents(model: BaseChatModel, session: AgentSession) -> dict[str, Any]:
    all_tools = build_tools(session)
    by_name = {t.name: t for t in all_tools}

    def _agent(name: str, prompt: str, tool_names: list[str]) -> Any:
        tools = [by_name[n] for n in tool_names]
        return create_agent(model, tools=tools, system_prompt=prompt, name=name)

    agents = {
        "auth": _agent(
            "auth_agent",
            "You handle authentication for the CareMatch system. "
            "If asked to log in, call login_to_carematch with the username and password "
            "the user provides. Once login succeeds, tell the user the system is ready.",
            ["login_to_carematch"],
        ),
        "trials": _agent(
            "trials_agent",
            "You manage clinical trial protocols in CareMatch. You can list, fetch, "
            "create, and update trials. When creating a trial from free-text protocol "
            "criteria, format protocol_text as bullet-point lines (one criterion per "
            "line, starting with '- ' or a numbered list) so the CareMatch parser can "
            "convert it into eligibility rules. Mark the section 'Inclusion criteria' "
            "or 'Exclusion criteria' explicitly, e.g.:\n"
            "'Inclusion criteria:\\n- Patient must be at least 18 years old\\n"
            "- Patient has diabetes\\nExclusion criteria:\\n- Patient is taking warfarin'.\n"
            "After creating, report the trial_id and how many rules were generated.",
            ["list_trials", "get_trial", "create_trial", "update_trial"],
        ),
        "eligibility": _agent(
            "eligibility_agent",
            "You evaluate whether a patient is eligible for a trial using CareMatch. "
            "Call list_trials or get_trial to find a trial_id, then evaluate_eligibility "
            "with the trial_id and a FHIR R4 JSON bundle. Summarize the per-rule "
            "evidence and the overall recommendation. Remember the assessment_id for "
            "follow-up review.",
            ["list_trials", "get_trial", "evaluate_eligibility"],
        ),
        "assessments": _agent(
            "assessments_agent",
            "You handle review of AI eligibility recommendations. You can list and get "
            "assessments, approve them, and override individual rule evaluations. "
            "Overrides REQUIRE reasoning of at least 5 characters. The AI recommendation "
            "is never final until a coordinator approves it.",
            ["list_assessments", "get_assessment", "approve_assessment", "override_rule"],
        ),
        "caregivers": _agent(
            "caregivers_agent",
            "You manage patient caregivers in CareMatch. You can list caregivers for a "
            "patient and register new caregivers with relationship types such as "
            "PRIMARY, EMERGENCY_CONTACT, LEGAL_PROXY, or POWER_OF_ATTORNEY.",
            ["list_caregivers_for_patient", "create_caregiver"],
        ),
        "audit": _agent(
            "audit_agent",
            "You provide compliance and operations information for CareMatch. You can "
            "read the audit trail and system metrics. Audit access requires an AUDITOR "
            "or ADMINISTRATOR account.",
            ["list_audit_logs", "get_metrics"],
        ),
    }
    return {"agents": agents, "run": _run_selector(agents), "tools": all_tools}


def _run_selector(agents: dict[str, Any]):
    """Returns a callable that runs a named subagent on a query."""

    def run(name: str, query: str) -> str:
        agent = agents.get(name)
        if agent is None:
            raise ValueError(f"Unknown subagent '{name}'")
        return _final_answer(agent, query)

    return run
