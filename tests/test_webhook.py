from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from app.events import NormalizedEvent
from app.webhook import WebhookClient


def sample_event() -> NormalizedEvent:
    return NormalizedEvent(
        type="message.created",
        chat_id=-100123,
        message_id=9,
        timestamp=datetime(2026, 9, 13, 9, 43, tzinfo=UTC),
        text="hello",
    )


@pytest.mark.asyncio
async def test_posts_normalized_json_and_delivery_headers() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(204)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    webhook = WebhookClient("http://webhook.test/events", client=client)

    delivered = await webhook.deliver(sample_event())
    await client.aclose()

    assert delivered is True
    assert json.loads(requests[0].content) == sample_event().to_dict()
    assert requests[0].headers["X-Telegram-Event-ID"] == sample_event().event_id


@pytest.mark.asyncio
async def test_retries_server_error_then_succeeds() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503 if attempts < 3 else 200)

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    webhook = WebhookClient(
        "http://webhook.test/events",
        client=client,
        max_attempts=5,
        backoff_seconds=0.5,
        sleep=fake_sleep,
    )

    delivered = await webhook.deliver(sample_event())
    await client.aclose()

    assert delivered is True
    assert attempts == 3
    assert delays == [0.5, 1.0]


@pytest.mark.asyncio
async def test_does_not_retry_permanent_client_error() -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    webhook = WebhookClient(
        "http://webhook.test/events",
        client=client,
        max_attempts=5,
    )

    delivered = await webhook.deliver(sample_event())
    await client.aclose()

    assert delivered is False
    assert attempts == 1


@pytest.mark.asyncio
async def test_retries_network_errors_up_to_limit() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("connection failed", request=request)

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    webhook = WebhookClient(
        "http://webhook.test/events",
        client=client,
        max_attempts=3,
        backoff_seconds=1,
        sleep=fake_sleep,
    )

    delivered = await webhook.deliver(sample_event())
    await client.aclose()

    assert delivered is False
    assert attempts == 3
    assert delays == [1, 2]
