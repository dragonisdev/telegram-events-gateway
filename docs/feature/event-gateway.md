# Event gateway behavior

## Data flow and boundaries

The service has three intentionally small layers:

1. `app/telegram_client.py` owns Telethon, subscribes to Telegram updates, applies
   the chat allowlist, and converts accepted updates into `NormalizedEvent`.
2. `app/events.py` defines the stable, transport-neutral event schema and event ID.
3. `app/webhook.py` serializes the normalized event and delivers it with HTTP POST.

No Telethon event, message, peer, or entity object crosses the integration-layer
boundary. This keeps downstream subscribers independent of Telethon's API.

## Supported events

The MVP emits two types:

- `message.created` for a newly created message
- `message.edited` for an edited message

Each payload contains:

| Field | Type | Meaning |
| --- | --- | --- |
| `type` | string | Stable event type |
| `chat_id` | integer | Telegram chat/channel ID |
| `message_id` | integer | Message ID within that chat |
| `timestamp` | string | UTC ISO 8601 event timestamp |
| `text` | string | Current message text, or an empty string |

Example:

```json
{
  "type": "message.edited",
  "chat_id": -1001234567890,
  "message_id": 1234,
  "timestamp": "2026-09-13T09:45:12Z",
  "text": "corrected message"
}
```

For edits, the gateway uses Telegram's edit timestamp when present and falls back
to the original message timestamp.

## Filtering

`TELEGRAM_ALLOWED_CHAT_IDS` is a comma-separated set of numeric Telegram IDs. The
allowlist is provided directly to Telethon's event builders and is checked again
before the gateway reads, logs, or delivers message text.

An event is filtered when its chat is not allowed or required metadata such as the
chat ID, message ID, or timestamp is missing. Filtered events produce structured
metadata logs and are not sent to the webhook.

## Webhook delivery

The configured `WEBHOOK_URL` receives a JSON `POST` with these headers:

```text
Content-Type: application/json
X-Telegram-Event-ID: <sha256-of-normalized-payload>
X-Telegram-Event-Type: message.created | message.edited
```

The event ID lets a subscriber deduplicate retries. Because the hash includes the
whole normalized payload, a genuine edit is not collapsed into the corresponding
create event.

Network errors, HTTP `408`, `425`, `429`, and `5xx` responses are retried. Other
`4xx` responses fail immediately. The delay doubles after each failed attempt and
is capped at 30 seconds; a numeric `Retry-After` on `429` is honored up to 60
seconds.

Delivery is at-least-once only within the in-memory retry window. There is no
durable queue, so:

- a subscriber must tolerate duplicate event IDs;
- an event is dropped after the final failed attempt;
- a process crash or redeploy can lose an event that was in flight; and
- messages sent while the gateway is offline are not guaranteed to be replayed.

These are deliberate MVP limits, not durability guarantees.

## Current local endpoint

The gateway only makes outbound connections to Telegram and `WEBHOOK_URL`. It does
not listen on an HTTP port and therefore does not expose an endpoint of its own.
For the current validation phase, the receiver is the included local test tool:

```dotenv
WEBHOOK_URL=http://127.0.0.1:8787/events
```

`tools/test_webhook.py` listens on that address, prints accepted JSON, and returns a
successful response. It is a validation aid, not a production subscriber.

Durable delivery and fan-out to multiple owned consumers are explicitly deferred.
Their intended sequence is documented in the
[future roadmap](../future/durable-delivery-and-broker.md).

## Logging

Logs are JSON and include operational metadata such as event type, chat ID,
message ID, attempt number, HTTP status, and error class. They do not intentionally
include message text, Telegram API credentials, session data, or the webhook URL.

The important log events are:

- `event.received`
- `event.filtered`
- `event.delivered`
- `event.delivery_retry`
- `event.failed`
- `telegram.connecting`, `telegram.connected`, and reconnect lifecycle events

Chat and message IDs are still metadata. Restrict access to logs if those
identifiers are sensitive in your threat model.
