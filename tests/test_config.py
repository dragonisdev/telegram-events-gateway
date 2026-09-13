from __future__ import annotations

import pytest

from app.config import ConfigError, Settings


def valid_env() -> dict[str, str]:
    return {
        "TELEGRAM_API_ID": "987654",
        "TELEGRAM_API_HASH": "secret-hash",
        "TELEGRAM_SESSION": "file:gateway",
        "TELEGRAM_ALLOWED_CHAT_IDS": "-1001234567890, 42, -1001234567890",
        "WEBHOOK_URL": "http://127.0.0.1:8787/events",
    }


def test_loads_and_parses_environment() -> None:
    settings = Settings.from_env(valid_env())

    assert settings.telegram_api_id == 987654
    assert settings.allowed_chat_ids == frozenset({-1001234567890, 42})
    assert settings.webhook_max_attempts == 5


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TELEGRAM_API_ID", "not-a-number"),
        ("TELEGRAM_ALLOWED_CHAT_IDS", "-1001,nope"),
        ("WEBHOOK_URL", "127.0.0.1:8787/events"),
    ],
)
def test_rejects_invalid_environment(name: str, value: str) -> None:
    env = valid_env()
    env[name] = value

    with pytest.raises(ConfigError):
        Settings.from_env(env)


def test_secret_values_are_omitted_from_repr() -> None:
    settings = Settings.from_env(valid_env())
    representation = repr(settings)

    assert "secret-hash" not in representation
    assert "file:gateway" not in representation
    assert "987654" not in representation
