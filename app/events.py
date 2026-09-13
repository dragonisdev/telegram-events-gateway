"""Transport-neutral event schema emitted by the gateway."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

EventType = Literal["message.created", "message.edited"]


@dataclass(frozen=True, slots=True)
class NormalizedEvent:
    type: EventType
    chat_id: int
    message_id: int
    timestamp: datetime
    text: str

    @property
    def event_id(self) -> str:
        """A stable identifier for retries of this exact normalized payload."""
        canonical = json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    def to_dict(self) -> dict[str, str | int]:
        timestamp = self.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        timestamp = timestamp.astimezone(UTC)
        return {
            "type": self.type,
            "chat_id": self.chat_id,
            "message_id": self.message_id,
            "timestamp": timestamp.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "text": self.text,
        }
