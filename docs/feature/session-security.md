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

A StringSession serializes the authorization into a single portable secret. It is
well suited to an ephemeral worker because every deployment can reconstruct the
authorized client from the environment without a volume.

The production choice for this MVP is:

```dotenv
TELEGRAM_SESSION=string:<generated-value>
```

stored as a sealed Railway variable. This removes the persistent-volume attack
surface, but it does not make the credential harmless: compromise of the runtime
or deployed code can still expose it.

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

## What a Railway sealed variable protects

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

For this small worker, accepting that residual runtime risk is a reasonable MVP
decision as long as it is explicit.

## Recommended controls

- Use a dedicated Telegram account that joins only the required chats.
- Store `TELEGRAM_SESSION`, `TELEGRAM_API_HASH`, and any credential-bearing webhook
  URL as sealed production variables.
- Never store a real StringSession in `.env.example`, Git, logs, tickets, or chat.
- Keep `.env`, `*.session`, and `*.session-journal` ignored by Git.
- Limit GitHub and Railway deployment permissions and enable account 2FA.
- Pin and review dependencies and deploy only reviewed commits.
- Keep the Railway worker private because it does not need inbound networking.
- Review Telegram's active devices periodically.
- Run one gateway replica to avoid duplicate listeners and webhook deliveries.

A dedicated account reduces the blast radius but does not create technical
read-only permissions. If a Telegram bot can be added to the source chat and its
available updates are sufficient, the Bot API provides a narrower identity. A
connected business bot may also fit some private-chat workflows. Those approaches
change Telegram capabilities and onboarding and are not implemented in this MVP.

## Incident response and rotation

If a session may have leaked:

1. Terminate that authorization in Telegram **Settings > Devices** immediately.
2. Generate a new StringSession locally.
3. Replace the sealed `TELEGRAM_SESSION` value in Railway and deploy it.
4. Review recent Telegram sessions, Railway deployments, and logs.
5. Rotate any webhook credential or other secret that may also have been exposed.

Do not rely on deleting the Railway variable alone: that prevents the gateway from
using the credential but does not revoke the Telegram authorization already copied
by an attacker.
