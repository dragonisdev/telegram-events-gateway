from __future__ import annotations

import logging

from app.logging_config import JsonFormatter


def test_json_formatter_redacts_sensitive_values() -> None:
    formatter = JsonFormatter(["api-secret", "session-secret"])
    record = logging.LogRecord(
        "test",
        logging.ERROR,
        __file__,
        1,
        "failed with %s",
        ("api-secret",),
        None,
    )
    record.session = "session-secret"

    encoded = formatter.format(record)

    assert "api-secret" not in encoded
    assert "session-secret" not in encoded
    assert encoded.count("[REDACTED]") == 2
