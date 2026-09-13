# Future: durable delivery and event broker

## Status

This document records follow-up work only. None of it is part of the current
implementation phase.

The active goal is limited to validating `message.created` and `message.edited`
locally with a dedicated test Telegram account and `tools/test_webhook.py`.

The future sequence is:

1. Add durable delivery using SQLite.
2. Add a broker service that supports multiple owned consumers.

AWS, SQS, PostgreSQL, Redis, customer subscriptions, MetaTrader trading logic, and
Discord bot logic are not planned for the current phase.

## Follow-up 1: SQLite durable delivery

The first expansion will prevent normalized events from disappearing merely
because the webhook is temporarily unavailable or the gateway restarts.

The intended design is a local SQLite outbox owned by the gateway:

```text
Telegram update
      |
      v
normalize event
      |
      v
commit to SQLite outbox
      |
      v
delivery worker -> webhook
```

An event is considered accepted internally only after the SQLite transaction
commits. A delivery worker then sends pending rows and records success or the next
retry time.

Expected capabilities:

- schema versioning and migrations;
- one stable `event_id` stored with every event;
- pending, delivered, and terminally failed delivery states;
- bounded exponential retry with persisted attempt counts;
- recovery of pending deliveries after restart;
- an explicit dead-letter state and manual replay command;
- configurable retention and cleanup;
- SQLite WAL mode and a busy timeout; and
- tests for crash/restart and duplicate-delivery behavior.

Delivery will remain at-least-once. Consumers must deduplicate by `event_id`; the
system will not claim exactly-once side effects.

This event outbox is separate from Telethon's `*.session` SQLite file. Telegram
authorization state and event-delivery state must never share a database.

## Follow-up 2: broker for owned consumers

After durable single-destination delivery is validated, introduce a broker service
for consumers operated by us. There will be no customer-facing signup or arbitrary
public subscription registration in the initial broker.

```text
Telegram gateway
      |
      v
authenticated broker ingestion
      |
      v
SQLite event store
      |
      +--> MetaTrader-related consumer delivery
      |
      +--> Discord-related consumer delivery
      |
      +--> future owned consumer delivery
```

The broker will:

- accept the stable normalized event contract from the gateway;
- authenticate ingestion from the gateway;
- store each accepted event durably before acknowledging it;
- keep trusted subscription definitions under our configuration control;
- filter subscriptions by permitted event type and chat ID;
- create an independent SQLite delivery row for every matching consumer;
- retry, dead-letter, inspect, and replay each consumer delivery independently;
- sign outgoing webhook deliveries; and
- expose only the minimum event data authorized for each consumer.

SQLite implies a single broker writer/service instance and a persistent disk. That
is acceptable for the expected low initial volume and cost goal. Backups, database
integrity checks, retention, and recovery procedures will be required before
calling it production-ready.

## Consumer transport decision

The broker transport will be chosen when the actual consumer interfaces are known:

- Webhooks are a natural fit for hosted services such as a Discord integration.
- Authenticated HTTP long polling may fit a MetaTrader terminal or local bridge.
- WebSockets may fit an existing companion application that already maintains a
  persistent connection.

No choice is required during local Telegram validation. Before implementing the
broker, inspect the existing MetaTrader-side program and decide which transport it
can consume reliably.

## Deferred operational decisions

Before either follow-up begins, define:

- required retention and acceptable data loss;
- event ordering requirements, especially create versus edit;
- retry limits and dead-letter handling;
- how SQLite is backed up and restored;
- how subscriber credentials are issued and rotated;
- whether the gateway outbox remains after the broker becomes authoritative; and
- where the single-instance broker will eventually run.
