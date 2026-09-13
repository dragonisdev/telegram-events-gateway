# telegram-event-gateway

`telegram-event-gateway` is a small, local-first Python service that signs in to
Telegram with a user account, listens only to an explicit chat allowlist, converts
Telethon updates into stable JSON, and delivers each event to an HTTP webhook.

The current phase is strictly local validation with a dedicated test Telegram
account and the included test webhook receiver. It is not being deployed or
connected to trading, Discord, or other production consumers yet.

```text
Telegram private chat/channel
            |
         Telethon
            |
  allowlist + normalization
            |
       HTTP POST webhook
            |
  local test receiver
```

The gateway is an outbound worker, not an inbound web API. During local validation,
`WEBHOOK_URL=http://127.0.0.1:8787/events` points to `tools/test_webhook.py` running
on the same computer.

## MVP capabilities

- Telegram user-account authentication through Telethon
- `message.created` and `message.edited` events
- an explicit numeric chat/channel allowlist
- a transport-neutral JSON event model
- bounded HTTP retries with exponential backoff
- automatic Telegram reconnect handling
- structured, secret-safe logging
- file-backed and environment-backed Telethon sessions
- tests with mocked Telegram events and HTTP responses

The project deliberately contains no delivery database, queue, broker, trading
logic, MetaTrader integration, Discord integration, signal parsing, or risk
management. Future durability will use SQLite rather than PostgreSQL, Redis, SQS,
or another hosted queue.

## Documentation

- [Event model and delivery behavior](docs/feature/event-gateway.md)
- [Telegram sessions, persistence, and security](docs/feature/session-security.md)
- [Local setup and acceptance test](docs/deployment/local.md)
- [Future durable delivery and event broker](docs/future/durable-delivery-and-broker.md)
- [Deferred Railway deployment notes](docs/deployment/railway.md)

## Quick start

Python 3.11 or newer and Telegram API credentials from
[my.telegram.org/apps](https://my.telegram.org/apps) are required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Complete `.env`, start the test receiver with `python tools/test_webhook.py`, and
then run the gateway in a second terminal with `python -m app.main`. See the
[local deployment guide](docs/deployment/local.md) for session setup and the full
acceptance check.

## Event contract

```json
{
  "type": "message.created",
  "chat_id": -1001234567890,
  "message_id": 1234,
  "timestamp": "2026-09-13T09:43:00Z",
  "text": "example message"
}
```

Telethon objects remain inside `app/telegram_client.py`. Downstream code receives
only the `NormalizedEvent` model defined in `app/events.py`.

## Verification

```powershell
pytest
ruff check .
```

The test suite never connects to Telegram or a real webhook.
