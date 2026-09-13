# Local setup and acceptance test

## Prerequisites

- Python 3.11 or newer
- Telegram API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)
- A dedicated test Telegram account
- A private test chat or channel accessible by that account

Do not use a primary personal account or production chat during this phase. The
goal is to validate Telegram event behavior locally, not to deploy the service.

## Install

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set the required values in `.env`:

```dotenv
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION=file:telegram-event-gateway
TELEGRAM_ALLOWED_CHAT_IDS=-1001234567890
WEBHOOK_URL=http://127.0.0.1:8787/events
```

`TELEGRAM_ALLOWED_CHAT_IDS` accepts comma-separated integers. Telegram channel IDs
normally use the `-100...` form.

## Authenticate and run

Start the included receiver in one terminal:

```powershell
python tools/test_webhook.py
```

Start the gateway in another:

```powershell
python -m app.main
```

On its first run with a new file session, Telethon asks for the account phone
number, Telegram login code, and two-step-verification password when applicable.
It creates `telegram-event-gateway.session`; later runs reuse that file without a
new code.

Both `.env` and Telethon session files are ignored by Git. Never commit or share
them.

The `*.session` file is Telethon's SQLite-backed authorization state. It is
separate from the future SQLite event/delivery store described in the
[roadmap](../future/durable-delivery-and-broker.md); no event database exists yet.

## Acceptance criterion

1. Send a message to an allowlisted private chat or channel.
2. Confirm that the receiver prints a `message.created` JSON payload.
3. Edit the Telegram message.
4. Confirm that the receiver prints a `message.edited` payload.
5. Confirm that no event is delivered from a chat outside the allowlist.
6. Stop and restart the gateway, then confirm the existing session reconnects
   without another login code.
7. Confirm structured logs contain event metadata but not message text or session
   data.

Stop either process with `Ctrl+C`.

## Configuration reference

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `TELEGRAM_API_ID` | yes | - | Telegram application ID |
| `TELEGRAM_API_HASH` | yes | - | Telegram application secret |
| `TELEGRAM_SESSION` | yes | - | `file:` or `string:` session configuration |
| `TELEGRAM_ALLOWED_CHAT_IDS` | yes | - | Comma-separated chat/channel IDs |
| `WEBHOOK_URL` | yes | - | Absolute HTTP(S) subscriber endpoint |
| `WEBHOOK_TIMEOUT_SECONDS` | no | `10` | Timeout per POST attempt |
| `WEBHOOK_MAX_ATTEMPTS` | no | `5` | Total attempts per event |
| `WEBHOOK_BACKOFF_SECONDS` | no | `1` | Initial exponential retry delay |
| `TELEGRAM_RECONNECT_BACKOFF_SECONDS` | no | `5` | Initial outer reconnect delay |
| `LOG_LEVEL` | no | `INFO` | Structured log threshold |

## Tests and lint

```powershell
pytest
ruff check .
```

The tests use mocked Telethon-shaped events and HTTPX transports. They do not
contact Telegram or a real webhook.

## Local validation boundary

Success in this phase means the event schema, filtering, edit handling, reconnect
behavior, local session persistence, retry behavior, and secret-safe logs have
been observed with test data. It does not establish production durability: events
can still be lost after retry exhaustion or while the process is offline.
