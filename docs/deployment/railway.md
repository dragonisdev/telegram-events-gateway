# Railway production deployment

## Production shape

Deploy this project as one long-running worker. It connects outbound to Telegram
and to the configured webhook; it does not run an HTTP server and does not need a
Railway public domain.

The destination URL belongs to the subscriber:

```text
Telegram -> Railway gateway -> WEBHOOK_URL -> subscriber
```

If the subscriber is another Railway service in the same project and environment,
prefer Railway private networking:

```dotenv
WEBHOOK_URL=http://event-subscriber.railway.internal:8080/telegram/events
```

Railway documents private service DNS as `<service-name>.railway.internal` and
keeps that traffic inside the project environment. Use `http`, not `https`, for
this internal address. See [Railway private networking](https://docs.railway.com/networking/private-networking).

If the subscriber is elsewhere, use its authenticated public HTTPS endpoint:

```dotenv
WEBHOOK_URL=https://subscriber.example.com/telegram/events
```

`localhost` on Railway means the gateway container itself. It cannot reach a
MetaTrader process running on a personal computer through
`http://127.0.0.1:...`; that receiver needs a reachable bridge, tunnel, VPN path,
or its own hosted service.

## 1. Generate the StringSession locally

Do this on a trusted local machine, not during a Railway build. With the project
environment activated, open Python and run:

```python
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 123456
api_hash = "replace_with_your_api_hash"

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print(client.session.save())
```

Telethon prompts for the phone number, login code, and two-step-verification
password if configured. Copy the single printed session string directly into
Railway. Treat terminal output and shell history around this operation as
sensitive. The official equivalent is documented under
[Telethon String Sessions](https://docs.telethon.dev/en/stable/concepts/sessions.html#string-sessions).

## 2. Create the Railway service

1. Create a Railway project and service from this GitHub repository.
2. Select `main` as the production deployment branch.
3. Set the start command to `python -m app.main` if Railway does not infer it.
4. Configure the restart policy as **Always** for a paid production worker, or
   **On Failure** where Always is unavailable.
5. Keep the service at one replica.
6. Do not generate a public domain for the gateway.

Railway's start command and restart behavior are described in its
[start-command](https://docs.railway.com/deployments/start-command) and
[restart-policy](https://docs.railway.com/deployments/restart-policy) documentation.

One replica avoids duplicate Telegram listeners and duplicate webhook deliveries.
Also leave deployment overlap at its default of zero unless the subscriber's event
deduplication has been verified.

## 3. Add variables

Add these service variables in the production environment:

```dotenv
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=replace_with_your_api_hash
TELEGRAM_SESSION=string:<the_generated_string>
TELEGRAM_ALLOWED_CHAT_IDS=-1001234567890
WEBHOOK_URL=https://subscriber.example.com/telegram/events
WEBHOOK_TIMEOUT_SECONDS=10
WEBHOOK_MAX_ATTEMPTS=5
WEBHOOK_BACKOFF_SECONDS=1
TELEGRAM_RECONNECT_BACKOFF_SECONDS=5
LOG_LEVEL=INFO
```

Seal at least:

- `TELEGRAM_API_HASH`
- `TELEGRAM_SESSION`
- `WEBHOOK_URL` when it embeds a credential or unguessable token

You may also seal the API ID and chat IDs to reduce metadata exposure. Sealed
variables cannot be read back, unsealed, or copied into preview/duplicated
environments, so keep a deliberate recovery and rotation process rather than
expecting Railway to reveal the original value later.

Railway supplies sealed values to the build and runtime as environment variables,
but never displays them in the UI or returns them through the API. The application
can and must read the plaintext at runtime; sealing is control-plane protection,
not a non-exportable hardware credential. See [Railway sealed variables](https://docs.railway.com/variables#sealed-variables) and the
[session security guide](../feature/session-security.md).

## 4. Deploy and verify

1. Apply the staged Railway variable changes and deploy.
2. Confirm logs contain `telegram.connected` without any credential or message
   text.
3. Send a message in an allowlisted chat.
4. Confirm the receiver gets `message.created` and returns a `2xx` response.
5. Edit the message and confirm `message.edited` arrives.
6. Send a test message in a non-allowlisted chat and confirm no webhook is sent.
7. Restart the Railway service and confirm it reconnects without asking for a new
   Telegram login code.

Because the session is stored in a Railway variable, no persistent volume is
required. Telethon will continue reusing the authorization across deployments
until Telegram or the user revokes it or it expires through inactivity.

## Security checklist

- Use a dedicated Telegram account with membership limited to required chats.
- Seal production secrets and use separate credentials in non-production.
- Keep the gateway off public networking.
- Restrict Railway and GitHub deployment access and enable 2FA.
- Enable **Wait for CI** before automatic production deployments when available.
- Review Telegram **Settings > Devices** periodically.
- Keep message text and session values out of logs.
- Revoke and regenerate the Telegram session immediately if compromise is
  suspected.

The detailed threat model, sealed-secret boundary, persistence behavior, and
rotation procedure are in [Telegram sessions and security](../feature/session-security.md).

## Current production limitations

- No durable queue or replay guarantee
- No webhook authentication header implemented by the gateway
- No health-check HTTP endpoint
- No database-backed audit history
- No exactly-once delivery guarantee

Those limitations are acceptable for the stated MVP, but webhook authentication
and durable delivery should be reconsidered before connecting the output directly
to an automated trading action.
