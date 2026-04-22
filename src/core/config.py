import os

from langchain_openai import ChatOpenAI


def get_llm(model: str = None) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=os.environ["LLAMA_CPP_BASE_URL"],
        model=model or os.environ.get("LLAMA_CPP_MODEL", "qwen3-coder-30b"),
        api_key="not-needed",
        temperature=0.2,
        max_tokens=2048,
    )
