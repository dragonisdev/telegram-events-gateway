"""Telethon integration and conversion into transport-neutral events."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from app.events import EventType, NormalizedEvent

logger = logging.getLogger(__name__)

EventConsumer = Callable[[NormalizedEvent], Awaitable[object]]


class TelegramEventSource:
    def __init__(
        self,
        *,
        api_id: int,
        api_hash: str,
        session: str,
        allowed_chat_ids: frozenset[int],
        on_event: EventConsumer,
        reconnect_backoff_seconds: float = 5.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._session = session
        self._allowed_chat_ids = allowed_chat_ids
        self._on_event = on_event
        self._initial_reconnect_backoff = reconnect_backoff_seconds
        self._sleep = sleep

    async def run_forever(self) -> None:
        client = TelegramClient(
            _telethon_session(self._session),
            self._api_id,
            self._api_hash,
            auto_reconnect=True,
            connection_retries=5,
            retry_delay=1,
            sequential_updates=True,
        )
        allowed_chats = list(self._allowed_chat_ids)
        client.add_event_handler(
            self._handle_new_message,
            events.NewMessage(chats=allowed_chats),
        )
        client.add_event_handler(
            self._handle_edited_message,
            events.MessageEdited(chats=allowed_chats),
        )

        reconnect_delay = self._initial_reconnect_backoff
        while True:
            try:
                logger.info("telegram.connecting")
                await client.start()
                account = await client.get_me()
                logger.info(
                    "telegram.connected",
                    extra={
                        "account_id": getattr(account, "id", None),
                        "allowed_chat_count": len(self._allowed_chat_ids),
                    },
                )
                reconnect_delay = self._initial_reconnect_backoff
                await client.run_until_disconnected()
                logger.warning("telegram.disconnected")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(
                    "telegram.connection_failed",
                    extra={"error_type": type(exc).__name__},
                )
            finally:
                await client.disconnect()

            logger.warning(
                "telegram.reconnect_scheduled",
                extra={"retry_in_seconds": reconnect_delay},
            )
            await self._sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 60.0)

    async def _handle_new_message(self, raw_event: Any) -> None:
        await self._handle_message(raw_event, "message.created")

    async def _handle_edited_message(self, raw_event: Any) -> None:
        await self._handle_message(raw_event, "message.edited")

    async def _handle_message(self, raw_event: Any, event_type: EventType) -> None:
        chat_id = _as_int(getattr(raw_event, "chat_id", None))
        if chat_id is None:
            logger.info(
                "event.filtered",
                extra={"event_type": event_type, "reason": "missing_chat_id"},
            )
            return
        if chat_id not in self._allowed_chat_ids:
            logger.info(
                "event.filtered",
                extra={
                    "event_type": event_type,
                    "chat_id": chat_id,
                    "reason": "chat_not_allowed",
                },
            )
            return

        message = getattr(raw_event, "message", None)
        if message is None:
            self._log_invalid(event_type, chat_id, "missing_message")
            return

        message_id = _as_int(getattr(message, "id", None))
        if message_id is None:
            self._log_invalid(event_type, chat_id, "missing_message_id")
            return

        timestamp = (
            getattr(message, "edit_date", None)
            if event_type == "message.edited"
            else getattr(message, "date", None)
        )
        if timestamp is None and event_type == "message.edited":
            timestamp = getattr(message, "date", None)
        if not isinstance(timestamp, datetime):
            self._log_invalid(
                event_type,
                chat_id,
                "missing_timestamp",
                message_id=message_id,
            )
            return

        text = getattr(message, "message", "")
        normalized = NormalizedEvent(
            type=event_type,
            chat_id=chat_id,
            message_id=message_id,
            timestamp=timestamp,
            text="" if text is None else str(text),
        )
        logger.info(
            "event.received",
            extra={
                "event_type": normalized.type,
                "chat_id": normalized.chat_id,
                "message_id": normalized.message_id,
            },
        )
        try:
            await self._on_event(normalized)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "event.failed",
                extra={
                    "event_type": normalized.type,
                    "chat_id": normalized.chat_id,
                    "message_id": normalized.message_id,
                    "reason": "consumer_error",
                    "error_type": type(exc).__name__,
                },
            )

    @staticmethod
    def _log_invalid(
        event_type: EventType,
        chat_id: int,
        reason: str,
        *,
        message_id: int | None = None,
    ) -> None:
        fields: dict[str, object] = {
            "event_type": event_type,
            "chat_id": chat_id,
            "reason": reason,
        }
        if message_id is not None:
            fields["message_id"] = message_id
        logger.info("event.filtered", extra=fields)


def _telethon_session(value: str) -> str | StringSession:
    if value.startswith("string:"):
        session_data = value.removeprefix("string:")
        if not session_data:
            raise ValueError("TELEGRAM_SESSION string value cannot be empty")
        return StringSession(session_data)
    if value.startswith("file:"):
        filename = value.removeprefix("file:")
        if not filename:
            raise ValueError("TELEGRAM_SESSION file value cannot be empty")
        return filename
    return value


def _as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
