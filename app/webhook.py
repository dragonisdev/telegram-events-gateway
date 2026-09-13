"""HTTP webhook delivery with bounded exponential retry."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Self

import httpx

from app.events import NormalizedEvent

logger = logging.getLogger(__name__)

Sleep = Callable[[float], Awaitable[None]]
_RETRYABLE_STATUS_CODES = {408, 425, 429}


class WebhookClient:
    def __init__(
        self,
        url: str,
        *,
        timeout_seconds: float = 10.0,
        max_attempts: int = 5,
        backoff_seconds: float = 1.0,
        client: httpx.AsyncClient | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._url = url
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=False,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def deliver(self, event: NormalizedEvent) -> bool:
        headers = {
            "Content-Type": "application/json",
            "X-Telegram-Event-ID": event.event_id,
            "X-Telegram-Event-Type": event.type,
        }

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._client.post(
                    self._url,
                    json=event.to_dict(),
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                if attempt < self._max_attempts:
                    delay = self._backoff_delay(attempt)
                    self._log_retry(
                        event,
                        attempt,
                        delay,
                        error_type=type(exc).__name__,
                    )
                    await self._sleep(delay)
                    continue
                self._log_failure(
                    event,
                    attempt,
                    reason="network_error",
                    error_type=type(exc).__name__,
                )
                return False

            if 200 <= response.status_code < 300:
                logger.info(
                    "event.delivered",
                    extra={
                        "event_type": event.type,
                        "chat_id": event.chat_id,
                        "message_id": event.message_id,
                        "attempt": attempt,
                        "status_code": response.status_code,
                    },
                )
                return True

            if (
                self._is_retryable(response.status_code)
                and attempt < self._max_attempts
            ):
                delay = self._response_delay(response, attempt)
                self._log_retry(
                    event,
                    attempt,
                    delay,
                    status_code=response.status_code,
                )
                await self._sleep(delay)
                continue

            self._log_failure(
                event,
                attempt,
                reason="http_error",
                status_code=response.status_code,
            )
            return False

        return False

    @staticmethod
    def _is_retryable(status_code: int) -> bool:
        return status_code in _RETRYABLE_STATUS_CODES or status_code >= 500

    def _backoff_delay(self, attempt: int) -> float:
        return min(self._backoff_seconds * (2 ** (attempt - 1)), 30.0)

    def _response_delay(self, response: httpx.Response, attempt: int) -> float:
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    return min(max(float(retry_after), 0.0), 60.0)
                except ValueError:
                    pass
        return self._backoff_delay(attempt)

    @staticmethod
    def _log_retry(
        event: NormalizedEvent,
        attempt: int,
        delay: float,
        *,
        status_code: int | None = None,
        error_type: str | None = None,
    ) -> None:
        fields: dict[str, object] = {
            "event_type": event.type,
            "chat_id": event.chat_id,
            "message_id": event.message_id,
            "attempt": attempt,
            "retry_in_seconds": delay,
        }
        if status_code is not None:
            fields["status_code"] = status_code
        if error_type is not None:
            fields["error_type"] = error_type
        logger.warning("event.delivery_retry", extra=fields)

    @staticmethod
    def _log_failure(
        event: NormalizedEvent,
        attempt: int,
        *,
        reason: str,
        status_code: int | None = None,
        error_type: str | None = None,
    ) -> None:
        fields: dict[str, object] = {
            "event_type": event.type,
            "chat_id": event.chat_id,
            "message_id": event.message_id,
            "attempt": attempt,
            "reason": reason,
        }
        if status_code is not None:
            fields["status_code"] = status_code
        if error_type is not None:
            fields["error_type"] = error_type
        logger.error("event.failed", extra=fields)
