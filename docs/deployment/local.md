# Local setup and acceptance test

## Prerequisites

- Python 3.11 or newer
- Telegram API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)
- A Telegram user account with access to every allowlisted chat

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

## Acceptance criterion

1. Send a message to an allowlisted private chat or channel.
2. Confirm that the receiver prints a `message.created` JSON payload.
3. Edit the Telegram message.
4. Confirm that the receiver prints a `message.edited` payload.
5. Confirm that no event is delivered from a chat outside the allowlist.

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
