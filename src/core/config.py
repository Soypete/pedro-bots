import os
import logging

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

VAULT_SECRETS_PATH = os.environ.get("VAULT_SECRETS_PATH", "/vault/secrets")


def get_secret(name: str) -> str | None:
    """Read secret from Vault secrets volume (file-based) or env var fallback."""
    for key in [name.lower(), name.upper(), name]:
        file_path = f"{VAULT_SECRETS_PATH}/{key}"
        if os.path.exists(file_path):
            with open(file_path) as f:
                return f.read().strip()
    for key in [name.lower(), name.upper(), name]:
        if key in os.environ:
            return os.environ[key]
    return None


def get_llm(model: str | None = None, max_tokens: int = 2048) -> ChatOpenAI:
    return ChatOpenAI(
        base_url=os.environ["LLAMA_CPP_BASE_URL"],
        model=model or os.environ.get("LLAMA_CPP_MODEL", "qwen3.6-27b-mtp"),
        max_completion_tokens=max_tokens,
        api_key="not-needed",
        temperature=0.2,
    )
