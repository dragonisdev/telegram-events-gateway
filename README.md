# telegram-event-gateway

A small local-first service that signs in with a Telegram **user account**, accepts
message events only from an explicit chat allowlist, normalizes them, and sends
them to an HTTP webhook.

The MVP handles:

- `message.created`
- `message.edited`
- private chats, groups, and channels identified by configured numeric chat IDs
- bounded webhook retries with exponential backoff
- Telethon reconnects plus an outer reconnect loop
- JSON logs that contain event metadata but never message text, Telegram API
  credentials, or session data

It deliberately has no database, queue, signal parsing, trading, MetaTrader, or
risk-management code.

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

Telegram/Telethon objects do not leave `app/telegram_client.py`. Everything after
that boundary receives the plain `NormalizedEvent` model from `app/events.py`.

## Prerequisites

- Python 3.11 or newer
- Telegram API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)
- A Telegram user account that can access every allowlisted chat

## Local setup

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edit `.env`:

```dotenv
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION=file:telegram-event-gateway
TELEGRAM_ALLOWED_CHAT_IDS=-1001234567890
WEBHOOK_URL=http://127.0.0.1:8787/events
```

`TELEGRAM_ALLOWED_CHAT_IDS` accepts comma-separated integer IDs. Telegram channel
IDs generally use the `-100...` form. The allowlist is checked before message text
is read, logged, or delivered.

### Session modes

- `file:telegram-event-gateway` (recommended) creates/uses
  `telegram-event-gateway.session` in the current directory. On the first run,
  Telethon prompts for the account phone number, login code, and 2FA password when
  applicable.
- `string:<Telethon StringSession>` keeps the session in the environment. Treat the
  entire value as a password.
- An unprefixed value is treated as a Telethon session filename for compatibility.

`.env` and `*.session` are ignored by Git. Never commit or paste either one into
logs or issue reports.

## Run the acceptance check

Start the included local webhook receiver in one terminal:

```powershell
python tools/test_webhook.py
```

Start the gateway in another terminal:

```powershell
python -m app.main
```

Send a message in an allowlisted private chat/channel. The webhook terminal should
print the normalized JSON. Edit the message to see a second payload whose type is
`message.edited`.

The gateway also sends `X-Telegram-Event-ID` and `X-Telegram-Event-Type` headers.
The event ID is a SHA-256 hash of the normalized payload, so consumers can use it
to deduplicate retries without collapsing distinct edits to the same message.
There is no durable queue in this MVP, so an event is dropped after all configured
webhook attempts fail.

Stop either process with `Ctrl+C`.

## Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `TELEGRAM_API_ID` | yes | - | Telegram application ID |
| `TELEGRAM_API_HASH` | yes | - | Telegram application secret |
| `TELEGRAM_SESSION` | yes | - | File or StringSession configuration |
| `TELEGRAM_ALLOWED_CHAT_IDS` | yes | - | Comma-separated chat/channel IDs |
| `WEBHOOK_URL` | yes | - | Absolute HTTP(S) endpoint |
| `WEBHOOK_TIMEOUT_SECONDS` | no | `10` | Timeout per POST attempt |
| `WEBHOOK_MAX_ATTEMPTS` | no | `5` | Total attempts per event |
| `WEBHOOK_BACKOFF_SECONDS` | no | `1` | Initial exponential retry delay |
| `TELEGRAM_RECONNECT_BACKOFF_SECONDS` | no | `5` | Initial outer reconnect delay |
| `LOG_LEVEL` | no | `INFO` | Structured log threshold |

Webhook delivery retries network failures, HTTP `408`, `425`, `429`, and all `5xx`
responses. Other `4xx` responses fail immediately. Backoff doubles between attempts
and is capped at 30 seconds; numeric `Retry-After` values on `429` responses are
honored up to 60 seconds.

## Tests and lint

The tests use mocked Telethon-shaped events and HTTPX mock transports; they do not
connect to Telegram or a real webhook.

```powershell
pytest
ruff check .
```
