import os

from langchain_openai import ChatOpenAI


def get_llm(model: str | None = None, max_tokens: int = 2048) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=os.environ["LLAMA_CPP_BASE_URL"],
        model=model or os.environ.get("LLAMA_CPP_MODEL", "qwen3.6-27b"),
        max_completion_tokens=max_tokens,
        api_key="not-needed",
        temperature=0.2,
    )
