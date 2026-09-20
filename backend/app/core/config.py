"""Validated settings for the dependencies actually introduced on Day 11."""

import re
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",  # The shared environment contract includes future integrations.
        frozen=True,
        hide_input_in_errors=True,
    )

    app_name: str = Field(default="ClaimAssist AI", min_length=1, max_length=100)
    app_env: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_allowed_origins: tuple[str, ...] = ()
    cors_allow_credentials: bool = False
    cors_allowed_methods: tuple[Literal["GET", "HEAD", "OPTIONS"], ...] = ("GET",)
    cors_allowed_headers: tuple[Literal["Content-Type", "X-Correlation-ID"], ...] = (
        "Content-Type",
        "X-Correlation-ID",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("app_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("APP_NAME must be nonblank and contain no control characters")
        return value

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_prefix(cls, value: str) -> str:
        if not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+", value):
            raise ValueError("API_V1_PREFIX must contain nonempty URL path segments")
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_origins(cls, origins: tuple[str, ...]) -> tuple[str, ...]:
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in origin
                or any(char.isspace() or ord(char) < 32 for char in origin)
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins without paths")
            _ = parsed.port  # Reject malformed or out-of-range ports at startup.
        return origins

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        if self.debug and self.app_env in {"staging", "production"}:
            raise ValueError("DEBUG must be false in deployed environments")
        return self
