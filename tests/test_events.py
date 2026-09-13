from datetime import UTC, datetime, timedelta, timezone

from app.events import NormalizedEvent


def test_serializes_stable_utc_schema() -> None:
    event = NormalizedEvent(
        type="message.created",
        chat_id=-1001234567890,
        message_id=1234,
        timestamp=datetime(2026, 9, 13, 12, 43, tzinfo=timezone(timedelta(hours=3))),
        text="example message",
    )

    assert event.to_dict() == {
        "type": "message.created",
        "chat_id": -1001234567890,
        "message_id": 1234,
        "timestamp": "2026-09-13T09:43:00Z",
        "text": "example message",
    }


def test_treats_naive_telegram_timestamp_as_utc() -> None:
    event = NormalizedEvent(
        type="message.edited",
        chat_id=1,
        message_id=2,
        timestamp=datetime(2026, 9, 13, 9, 43),
        text="edited",
    )

    assert event.to_dict()["timestamp"] == datetime(
        2026, 9, 13, 9, 43, tzinfo=UTC
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_event_id_is_stable_for_retries_but_changes_with_payload() -> None:
    original = NormalizedEvent(
        type="message.edited",
        chat_id=1,
        message_id=2,
        timestamp=datetime(2026, 9, 13, 9, 43, tzinfo=UTC),
        text="first edit",
    )
    later_edit = NormalizedEvent(
        type="message.edited",
        chat_id=1,
        message_id=2,
        timestamp=datetime(2026, 9, 13, 9, 43, tzinfo=UTC),
        text="second edit",
    )

    assert original.event_id == original.event_id
    assert original.event_id != later_edit.event_id
    assert len(original.event_id) == 64
