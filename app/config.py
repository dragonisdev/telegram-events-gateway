"""Environment-based configuration with validation and secret-safe reprs."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlparse


class ConfigError(ValueError):
    """Raised when required configuration is absent or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    telegram_api_id: int = field(repr=False)
    telegram_api_hash: str = field(repr=False)
    telegram_session: str = field(repr=False)
    allowed_chat_ids: frozenset[int]
    webhook_url: str = field(repr=False)
    webhook_timeout_seconds: float = 10.0
    webhook_max_attempts: int = 5
    webhook_backoff_seconds: float = 1.0
    telegram_reconnect_backoff_seconds: float = 5.0
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        source = os.environ if environ is None else environ

        api_id = _positive_int(source, "TELEGRAM_API_ID")
        api_hash = _required(source, "TELEGRAM_API_HASH")
        session = _required(source, "TELEGRAM_SESSION")
        allowed_chat_ids = _chat_ids(source)
        webhook_url = _http_url(source, "WEBHOOK_URL")
        timeout = _positive_float(source, "WEBHOOK_TIMEOUT_SECONDS", 10.0)
        max_attempts = _positive_int(source, "WEBHOOK_MAX_ATTEMPTS", 5)
        webhook_backoff = _non_negative_float(source, "WEBHOOK_BACKOFF_SECONDS", 1.0)
        reconnect_backoff = _positive_float(
            source, "TELEGRAM_RECONNECT_BACKOFF_SECONDS", 5.0
        )
        log_level = source.get("LOG_LEVEL", "INFO").strip().upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigError("LOG_LEVEL must be a standard Python log level")

        return cls(
            telegram_api_id=api_id,
            telegram_api_hash=api_hash,
            telegram_session=session,
            allowed_chat_ids=allowed_chat_ids,
            webhook_url=webhook_url,
            webhook_timeout_seconds=timeout,
            webhook_max_attempts=max_attempts,
            webhook_backoff_seconds=webhook_backoff,
            telegram_reconnect_backoff_seconds=reconnect_backoff,
            log_level=log_level,
        )


def _required(source: Mapping[str, str], name: str) -> str:
    value = source.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is required")
    return value


def _positive_int(
    source: Mapping[str, str], name: str, default: int | None = None
) -> int:
    raw = source.get(name)
    if raw is None and default is not None:
        return default
    if raw is None or not raw.strip():
        raise ConfigError(f"{name} is required")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if value < 1:
        raise ConfigError(f"{name} must be greater than zero")
    return value


def _positive_float(source: Mapping[str, str], name: str, default: float) -> float:
    raw = source.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be greater than zero")
    return value


def _non_negative_float(source: Mapping[str, str], name: str, default: float) -> float:
    raw = source.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc
    if value < 0:
        raise ConfigError(f"{name} must be zero or greater")
    return value


def _chat_ids(source: Mapping[str, str]) -> frozenset[int]:
    raw = _required(source, "TELEGRAM_ALLOWED_CHAT_IDS")
    parsed: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            raise ConfigError(
                "TELEGRAM_ALLOWED_CHAT_IDS must be a comma-separated list of integers"
            )
        try:
            parsed.add(int(item))
        except ValueError as exc:
            raise ConfigError(
                "TELEGRAM_ALLOWED_CHAT_IDS must be a comma-separated list of integers"
            ) from exc
    return frozenset(parsed)


def _http_url(source: Mapping[str, str], name: str) -> str:
    value = _required(source, name)
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError(f"{name} must be an absolute http:// or https:// URL")
    return value
