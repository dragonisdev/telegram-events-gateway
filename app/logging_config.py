"""Minimal JSON logging without event text or credential fields."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime

_STANDARD_FIELDS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


class JsonFormatter(logging.Formatter):
    def __init__(self, sensitive_values: Iterable[str] = ()) -> None:
        super().__init__()
        self._sensitive_values = tuple(
            sorted(
                (value for value in sensitive_values if value), key=len, reverse=True
            )
        )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        for name, value in record.__dict__.items():
            if name not in _STANDARD_FIELDS and not name.startswith("_"):
                payload[name] = value
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        encoded = json.dumps(payload, default=str, separators=(",", ":"))
        for sensitive_value in self._sensitive_values:
            escaped_value = json.dumps(sensitive_value)[1:-1]
            encoded = encoded.replace(escaped_value, "[REDACTED]")
            encoded = encoded.replace(sensitive_value, "[REDACTED]")
        return encoded


def configure_logging(
    level: str = "INFO", sensitive_values: Iterable[str] = ()
) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(sensitive_values))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Third-party INFO/DEBUG logs may include request or connection details. The
    # gateway emits its own metadata-only records instead.
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
