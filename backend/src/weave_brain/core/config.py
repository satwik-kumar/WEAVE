"""Settings shared by application entry points."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".env", ROOT / "backend" / ".env"),
        extra="ignore",
    )
    allowed_origins: str = "http://localhost:5173"
    development_fixtures: bool = False
    falkordb_host: str | None = None
    falkordb_port: int = Field(default=6379, ge=1, le=65535)
    falkordb_graph_name: str | None = None
    falkordb_username: str | None = None
    falkordb_password: SecretStr | None = None
    falkordb_ssl: bool = False
    falkordb_timeout: float = Field(default=5, gt=0, le=30)
    chat_mode: Literal["retrieval", "agent"] = "retrieval"
    llm_provider: Literal[
        "deterministic",
        "groq",
        "gemini",
        "openrouter",
        "ollama",
        "anthropic",
        "openai",
    ] = "deterministic"
    llm_model: str = ""
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_timeout: float = Field(default=20, gt=0, le=60)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    groq_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, value: str) -> str:
        origins = (
            json.loads(value) if value.strip().startswith("[") else value.split(",")
        )
        if (
            not isinstance(origins, list)
            or not origins
            or any(
                not isinstance(origin, str)
                or not origin.strip().startswith(("http://", "https://"))
                for origin in origins
            )
        ):
            raise ValueError("ALLOWED_ORIGINS must contain HTTP origins")
        for origin in origins:
            parsed = urlsplit(origin.strip())
            if (
                not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path not in ("", "/")
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("ALLOWED_ORIGINS must contain origins only")
        return ",".join(origin.strip().rstrip("/") for origin in origins)

    @property
    def origins(self) -> list[str]:
        return self.allowed_origins.split(",")


@lru_cache
def get_settings() -> Settings:
    return Settings()
