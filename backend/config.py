from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-opus-4-6"
    MAX_FILE_SIZE_MB: int = 50
    MAX_FILES: int = 20
    PORT: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
