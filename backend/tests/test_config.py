from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from app.core.config import Settings
from app.main import create_app


def test_safe_defaults() -> None:
    settings = Settings()
    assert settings.app_name == "ClaimAssist AI"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.cors_allowed_origins == ()
    assert not settings.cors_allow_credentials
    assert not settings.debug


def test_environment_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Configured App")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("API_V1_PREFIX", "/service/v1")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:3000"]')
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = Settings()
    assert settings.app_name == "Configured App"
    assert settings.api_v1_prefix == "/service/v1"
    assert settings.cors_allowed_origins == ("http://localhost:3000",)
    assert settings.log_level == "DEBUG"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("APP_NAME", "   "),
        ("APP_NAME", "unsafe\nname"),
        ("APP_ENV", "unknown"),
        ("DEBUG", "perhaps"),
        ("LOG_LEVEL", "verbose"),
        ("API_V1_PREFIX", "api/v1"),
        ("API_V1_PREFIX", "/api/v1/"),
        ("API_V1_PREFIX", "/api?secret=value"),
        ("CORS_ALLOWED_ORIGINS", '["*"]'),
        ("CORS_ALLOWED_ORIGINS", '["https://*.example.test"]'),
        ("CORS_ALLOWED_ORIGINS", '["ftp://example.test"]'),
        ("CORS_ALLOWED_ORIGINS", '["https://user:password@example.test"]'),
        ("CORS_ALLOWED_ORIGINS", '["https://example.test/path"]'),
        ("CORS_ALLOWED_ORIGINS", '["https://example.test?query=value"]'),
        ("CORS_ALLOWED_ORIGINS", '["https://example.test#fragment"]'),
        ("CORS_ALLOWED_ORIGINS", '["https://example.test:99999"]'),
        ("CORS_ALLOWED_ORIGINS", '["https://bad host.test"]'),
        ("CORS_ALLOWED_ORIGINS", "not-json"),
        ("CORS_ALLOWED_METHODS", '["*"]'),
        ("CORS_ALLOWED_HEADERS", '["*"]'),
    ],
)
def test_invalid_configuration_fails_startup(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises((ValidationError, SettingsError)):
        create_app()


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_deployed_debug_is_rejected(monkeypatch: pytest.MonkeyPatch, environment: str) -> None:
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("DEBUG", "true")
    with pytest.raises(ValidationError, match="DEBUG must be false"):
        Settings()


def test_development_debug_does_not_enable_traceback_pages() -> None:
    app = create_app(Settings(debug=True))
    assert app.debug is False


def test_environment_overrides_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("APP_NAME=From dotenv\nFUTURE_SETTING=ignored\n", encoding="utf-8")
    monkeypatch.setitem(Settings.model_config, "env_file", dotenv)
    assert Settings().app_name == "From dotenv"
    monkeypatch.setenv("APP_NAME", "From environment")
    assert Settings().app_name == "From environment"


def test_example_environment_is_usable(monkeypatch: pytest.MonkeyPatch) -> None:
    example = Path(__file__).resolve().parents[2] / ".env.example"
    monkeypatch.setitem(Settings.model_config, "env_file", example)
    assert Settings().app_name == "ClaimAssist AI"


def test_empty_optional_environment_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "")
    assert Settings().cors_allowed_origins == ()
