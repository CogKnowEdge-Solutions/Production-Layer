from langchain_openai import ChatOpenAI


def build_model(model_name: str, api_key: str, temperature: float = 0.2) -> ChatOpenAI:
    """ChatOpenAI pointed at OpenRouter's API, using a (preferably free) model.

    Free models (e.g. 'openai/gpt-oss-20b:free') are rate-limited and can be
    flaky upstream, so we retry aggressively and tolerate slow first tokens.
    Swap OPENROUTER_MODEL in .env for any other model.
    """
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,  # type: ignore[arg-type]
        base_url="https://openrouter.ai/api/v1",
        temperature=temperature,
        max_tokens=1024,  # type: ignore[call-arg]
        max_retries=4,
        timeout=90,
        default_headers={"HTTP-Referer": "http://localhost", "X-Title": "CareMatch Agent"},
    )
