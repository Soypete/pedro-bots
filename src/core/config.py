import os

from langchain_openai import ChatOpenAI


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=os.environ["LLAMA_CPP_BASE_URL"],
        model=os.environ["LLAMA_CPP_MODEL"],
        api_key="not-needed",
        temperature=0.2,
        max_tokens=2048,
    )
