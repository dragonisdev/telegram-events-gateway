# Telegram sessions and security

## What a Telethon session is

The Telegram API ID and API hash identify the Telegram application. The Telethon
session is the authorization created after a user signs in with a phone number,
login code, and, when enabled, Telegram two-step verification.

The session contains an authorization key that is sufficient to reconnect without
requesting a new login code. Telethon describes a `StringSession` as an exported
authorization key and warns that anyone holding it can sign in as that account.
See [Telethon's session documentation](https://docs.telethon.dev/en/stable/concepts/sessions.html).

This means a user session should be handled like a high-value password. Telegram
user sessions do not provide application-level read-only or per-chat scopes. The
gateway's allowlist restricts what this application processes; it does not reduce
what a stolen user session is technically authorized to access.

## Session modes

The gateway accepts these `TELEGRAM_SESSION` forms:

```dotenv
# SQLite session file; Telethon creates telegram-event-gateway.session
TELEGRAM_SESSION=file:telegram-event-gateway

# Portable authorization stored in an environment variable
TELEGRAM_SESSION=string:<Telethon StringSession>
```

An unprefixed value is treated as a Telethon session filename for compatibility.

### File session

A file session persists both authorization and Telethon's changing session state
on disk. It is convenient locally. On an ephemeral hosting platform it requires a
persistent volume, and possession of the session file grants the same account
access as possession of a StringSession.

### StringSession

A StringSession serializes the authorization into a single portable secret. It can
later support an ephemeral worker because a deployment can reconstruct the
authorized client from the environment without a volume.

StringSession deployment is deferred. The current local-validation choice is:

```dotenv
TELEGRAM_SESSION=file:telegram-event-gateway
```

Use it only with the dedicated test account. The resulting file persists between
local runs and must remain outside Git.

## Persistence and reauthentication

Telethon does not normally require periodic reauthentication. Once a session is
authorized, restarts and redeployments reuse it without another Telegram code.
Telethon notes that an existing session contains enough information to log in
without resending the code.

Reauthentication becomes necessary when:

- the session is terminated from Telegram's **Settings > Devices** screen;
- Telegram invalidates the authorization after a security or account event;
- Telegram's inactive-session time-to-live expires;
- the saved session is missing, replaced, or corrupted; or
- the StringSession variable is changed to an invalid value.

Telegram exposes an authorization inactivity TTL, documented as a number of days
in [`account.setAuthorizationTTL`](https://core.telegram.org/method/account.setAuthorizationTTL).
An actively connected gateway would not ordinarily age out as an inactive session.

Two-step verification protects creation of a new authorization. It does not ask
for a second factor on every request made through an already authorized session,
so it does not neutralize a copied session key.

## Deferred hosting note: sealed variables

A future Railway deployment may use a StringSession stored as a sealed variable.
A sealed variable is write-only from Railway's control plane. Railway provides its
value to builds and running deployments, but does not display it in the dashboard
or return it through the API. Sealed values also are not returned by
`railway variables`/`railway run` and are not copied to PR environments, duplicated
services, or duplicated environments. See [Railway's variable documentation](https://docs.railway.com/variables).

Sealing does **not** make the secret opaque to this application. At runtime:

1. Railway injects `TELEGRAM_SESSION` as an environment variable.
2. The Python process reads its plaintext value.
3. Telethon reconstructs the authorization in memory.

Consequently, malicious deployed code, a compromised dependency, a runtime
intrusion, or someone able to deploy arbitrary diagnostic code could extract the
session. Sealing primarily protects against dashboard/API readback, leaked
control-plane credentials, accidental copying, and exposure to preview services.
Because Railway also provides variables during builds, repository and dependency
integrity are part of the security boundary.

This risk decision is retained for future reference only. No Railway deployment is
part of the current local-validation phase.

## Recommended controls

- Use a dedicated test Telegram account that joins only test chats.
- Never store a real StringSession in `.env.example`, Git, logs, tickets, or chat.
- Keep `.env`, `*.session`, and `*.session-journal` ignored by Git.
- Limit access to the local machine and enable Telegram two-step verification.
- Pin and review dependencies.
- Review Telegram's active devices periodically.
- Do not connect the test account to production or sensitive chats.

A dedicated account reduces the blast radius but does not create technical
read-only permissions. If a Telegram bot can be added to the source chat and its
available updates are sufficient, the Bot API provides a narrower identity. A
connected business bot may also fit some private-chat workflows. Those approaches
change Telegram capabilities and onboarding and are not implemented in this MVP.

## Incident response and rotation

If the local test session may have leaked:

1. Terminate that authorization in Telegram **Settings > Devices** immediately.
2. Delete the local test session file after confirming its exact path.
3. Start the gateway and authenticate the test account again to create a new
   session.
4. Review recent Telegram sessions and local logs.
5. Rotate any other secret that may also have been exposed.

Deleting the local file alone is insufficient if someone copied it. Terminating the
authorization in Telegram is what invalidates the stolen session.
