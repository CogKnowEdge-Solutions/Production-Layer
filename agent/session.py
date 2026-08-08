"""Shared mutable session for a single agent conversation.

The coordinator and all subagents operate on the same session object, so a
token obtained by the auth subagent is available to every other tool.
"""

from dataclasses import dataclass, field


@dataclass
class AgentSession:
    base_url: str = "http://localhost:8000"
    token: str | None = None
    last_result: str = ""
    notes: list[str] = field(default_factory=list)

    def has_token(self) -> bool:
        return bool(self.token)

    def token_or_raise(self) -> str:
        """Return the auth token or raise a clear error for the LLM to see."""
        if not self.token:
            raise RuntimeError(
                "Not authenticated. Ask the user for credentials and call login_to_carematch first."
            )
        return self.token
