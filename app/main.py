"""Application entry point."""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

from app.config import ConfigError, Settings
from app.logging_config import configure_logging
from app.telegram_client import TelegramEventSource
from app.webhook import WebhookClient

logger = logging.getLogger(__name__)


async def run(settings: Settings) -> None:
    logger.info(
        "gateway.starting",
        extra={"allowed_chat_count": len(settings.allowed_chat_ids)},
    )
    async with WebhookClient(
        settings.webhook_url,
        timeout_seconds=settings.webhook_timeout_seconds,
        max_attempts=settings.webhook_max_attempts,
        backoff_seconds=settings.webhook_backoff_seconds,
    ) as webhook:
        telegram = TelegramEventSource(
            api_id=settings.telegram_api_id,
            api_hash=settings.telegram_api_hash,
            session=settings.telegram_session,
            allowed_chat_ids=settings.allowed_chat_ids,
            on_event=webhook.deliver,
            reconnect_backoff_seconds=settings.telegram_reconnect_backoff_seconds,
        )
        await telegram.run_forever()


def cli() -> int:
    load_dotenv()
    fallback_level = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    if fallback_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        fallback_level = "INFO"

    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        configure_logging(fallback_level)
        logger.error("configuration.invalid", extra={"reason": str(exc)})
        return 2

    session_value = settings.telegram_session.removeprefix("string:")
    configure_logging(
        settings.log_level,
        sensitive_values=(
            str(settings.telegram_api_id),
            settings.telegram_api_hash,
            settings.telegram_session,
            session_value,
            settings.webhook_url,
        ),
    )
    try:
        asyncio.run(run(settings))
    except KeyboardInterrupt:
        logger.info("gateway.stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
