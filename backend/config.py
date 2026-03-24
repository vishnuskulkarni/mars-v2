from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Literal


class Settings(BaseSettings):
    # LLM Provider: "ollama" (free, local) or "anthropic" (paid, cloud)
    LLM_PROVIDER: Literal["ollama", "anthropic"] = "ollama"

    # Ollama settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"

    # Anthropic settings (only used if LLM_PROVIDER=anthropic)
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-opus-4-6"

    # General settings
    MAX_FILE_SIZE_MB: int = 50
    MAX_FILES: int = 20
    PORT: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
