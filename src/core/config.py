import os

from langchain_openai import ChatOpenAI


def get_llm(model: str | None = None) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=os.environ["LLAMA_CPP_BASE_URL"],
        model=model or os.environ.get("LLAMA_CPP_MODEL", "qwen3.6-27b"),
        max_completion_tokens=2048,
        api_key="not-needed",
        temperature=0.2,
        max_tokens=2048,
    )
