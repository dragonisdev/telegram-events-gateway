from __future__ import annotations

import logging
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.events import NormalizedEvent
from app.telegram_client import TelegramEventSource


def source_for(
    delivered: list[NormalizedEvent], allowed_chat_ids: frozenset[int]
) -> TelegramEventSource:
    async def collect(event: NormalizedEvent) -> None:
        delivered.append(event)

    return TelegramEventSource(
        api_id=123,
        api_hash="secret",
        session="file:test",
        allowed_chat_ids=allowed_chat_ids,
        on_event=collect,
    )


@pytest.mark.asyncio
async def test_normalizes_created_message_from_mock_event() -> None:
    delivered: list[NormalizedEvent] = []
    source = source_for(delivered, frozenset({-100123}))
    raw_event = SimpleNamespace(
        chat_id=-100123,
        message=SimpleNamespace(
            id=99,
            date=datetime(2026, 9, 13, 9, 43, tzinfo=UTC),
            edit_date=None,
            message="hello",
        ),
    )

    await source._handle_new_message(raw_event)

    assert len(delivered) == 1
    assert delivered[0].to_dict() == {
        "type": "message.created",
        "chat_id": -100123,
        "message_id": 99,
        "timestamp": "2026-09-13T09:43:00Z",
        "text": "hello",
    }


@pytest.mark.asyncio
async def test_edited_message_uses_edit_timestamp() -> None:
    delivered: list[NormalizedEvent] = []
    source = source_for(delivered, frozenset({7}))
    edited_at = datetime(2026, 9, 13, 10, 0, tzinfo=UTC)
    raw_event = SimpleNamespace(
        chat_id=7,
        message=SimpleNamespace(
            id=11,
            date=datetime(2026, 9, 13, 9, 0, tzinfo=UTC),
            edit_date=edited_at,
            message="changed",
        ),
    )

    await source._handle_edited_message(raw_event)

    assert delivered[0].type == "message.edited"
    assert delivered[0].timestamp == edited_at


@pytest.mark.asyncio
async def test_filters_non_allowlisted_chat_without_reading_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    delivered: list[NormalizedEvent] = []
    source = source_for(delivered, frozenset({7}))
    raw_event = SimpleNamespace(chat_id=8)

    with caplog.at_level(logging.INFO):
        await source._handle_new_message(raw_event)

    assert delivered == []
    record = next(record for record in caplog.records if record.msg == "event.filtered")
    assert record.reason == "chat_not_allowed"
    assert record.chat_id == 8
