from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.config import AgentSettings, get_agent_settings
from agent.coordinator import build_coordinator
from agent.model import build_model
from agent.session import AgentSession


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message to the coordinator agent")
    username: str | None = None
    password: str | None = None


class ChatResponse(BaseModel):
    response: str


def create_agent_app(settings: AgentSettings | None = None) -> FastAPI:
    settings = settings or get_agent_settings()
    app = FastAPI(
        title="CareMatch Agent",
        description=(
            "LangChain coordinator agent that delegates work to specialized subagents "
            "which call the CareMatch API tools."
        ),
        version="1.0.0",
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    @app.post("/agent/chat", response_model=ChatResponse)
    def chat(body: ChatRequest):
        if not settings.openrouter_api_key:
            raise HTTPException(
                status_code=500,
                detail="OPENROUTER_API_KEY is not configured in .env",
            )

        session = AgentSession(base_url=settings.agent_api_url)
        if body.username and body.password:
            session.token = None  # auth subagent will log in

        try:
            model = build_model(settings.openrouter_model, settings.openrouter_api_key)
            coordinator = build_coordinator(model, session)
            prompt = body.message
            if body.username and body.password:
                prompt = (
                    f"Credentials provided by user: username='{body.username}', "
                    f"password='{body.password}'. "
                    f"Log the user in first, then handle: {body.message}"
                )
            result = coordinator.invoke({"messages": [{"role": "user", "content": prompt}]})
            messages = result.get("messages", [])
            answer = messages[-1].content if messages else "No response from coordinator."
            return ChatResponse(response=str(answer))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

    @app.get("/agent/health")
    def health():
        configured = bool(settings.openrouter_api_key)
        return {
            "status": "ok",
            "model": settings.openrouter_model,
            "api_url": settings.agent_api_url,
            "openrouter_configured": configured,
        }

    return app


app = create_agent_app()
