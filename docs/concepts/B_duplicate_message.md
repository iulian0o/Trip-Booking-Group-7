# Duplicate-message handling

## Category: B

## Problem
The notification worker calls insert_notification() for every message it
receives from RabbitMQ. The trip-service can publish the same event_id
twice (publish_event_twice simulation, or a real redelivery after a
worker crash). Because the baseline insert had no uniqueness check on
event_id, each delivery produced a separate row. One trip booking
resulted in two identical notifications in the database.

## Invariant or guarantee
For any given event_id, exactly one notification row exists in the
database, regardless of how many times that message is delivered by
the broker.

## Modified files
```
- notification_api/db.py: unique constraint on event_id, INSERT ON CONFLICT DO NOTHING
- notification_worker/worker.py: checks return value of insert_notification, logs skipped duplicates
```

## Behavior before
publish_event_twice=True → worker consumes two messages → two rows
inserted with the same event_id → user receives two notifications
for the same trip booking.

## Behavior after
publish_event_twice=True → worker consumes two messages → first
message inserts the row → second message hits the UNIQUE constraint,
insert_notification returns None → worker logs "duplicate skipped"
and acknowledges the message → exactly one notification row exists.

## How to test
```bash
docker compose down -v
docker compose up --build -d
docker compose run --rm tools python scripts/demo_duplicate_notification.py
```
Expected output: "PASS: exactly 1 notification stored despite 2 message deliveries."

## Limitation
- The UNIQUE constraint deduplicates by event_id. If the upstream
  publisher generates a new event_id for what is logically the same
  trip confirmation (e.g. after a crash and replay), the worker will
  store a second notification and consider it a new event. True
  end-to-end deduplication would require a trip-level idempotency key
  instead of an event-level one.
- The worker acknowledges duplicate messages. If the broker redelivers
  a message because the worker crashed after insert but before ack
  (CRASH_ONCE_AFTER_INSERT_BEFORE_ACK), the second delivery is safely
  skipped by the constraint — this is the correct behavior.