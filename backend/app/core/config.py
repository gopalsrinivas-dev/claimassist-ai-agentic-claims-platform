"""Validated settings; database credentials remain secret at every display boundary."""

import re
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    Field,
    ModelWrapValidatorHandler,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_core import InitErrorDetails
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
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
    database_url: SecretStr = Field(repr=False)
    sql_echo: bool = False

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            raw = value.get_secret_value()
            url = make_url(raw)
            if (
                url.drivername not in {"postgresql", "postgresql+psycopg"}
                or not url.host
                or not url.database
                or (url.port is not None and not 1 <= url.port <= 65535)
                or any(char.isspace() or ord(char) < 32 for char in raw)
            ):
                raise ValueError("Invalid database configuration")
        except (ArgumentError, ValueError):
            raise ValueError("DATABASE_URL must be a valid PostgreSQL connection URL") from None
        return value

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

    @model_validator(mode="wrap")
    @classmethod
    def hide_configuration_inputs(
        cls, data: object, handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        # Must wrap field AND model validators: model errors contain all inputs.
        try:
            return handler(data)
        except ValidationError as exc:
            # hide_input_in_errors only protects str(exc), not errors()/json().
            errors: list[InitErrorDetails] = []
            for error in exc.errors(include_input=False, include_url=False):
                detail: InitErrorDetails = {
                    "type": error["type"],
                    "loc": error["loc"],
                    "input": "<redacted>",
                }
                if "ctx" in error:
                    detail["ctx"] = error["ctx"]
                errors.append(detail)
            raise ValidationError.from_exception_data(
                cls.__name__, errors, hide_input=True
            ) from None
