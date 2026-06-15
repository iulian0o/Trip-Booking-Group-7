# Database Transaction

## Category

A — A1: Integrity and atomicity

## Problem

In the baseline application, the flight booking and hotel reservation endpoints
performed three separate database operations with no transaction:
1. Read available inventory
2. Decrement inventory
3. Insert booking/reservation row

If the service crashed between any of these steps, the database could be left in
an invalid state — for example, inventory decremented but no booking record created.

## Invariant or guarantee

Either all three operations succeed together, or none of them are applied.
No partial state is ever visible in the database.

## Modified files

- `flight_service/main.py`
- `hotel_service/main.py`

## Behavior before

A crash or exception after the UPDATE but before the INSERT would decrement
seats or rooms without creating a booking record, leaving inventory permanently
reduced with no corresponding booking.

## Behavior after

All operations run inside a single transaction. If any step fails, PostgreSQL
rolls back the entire transaction and the inventory remains unchanged.

## How to test

```bash
docker compose run --rm tools python scripts/demo_partial_failure.py
```

Also run the smoke test to verify the happy path still works:

```bash
docker compose run --rm tools pytest tests/test_smoke.py
```

## Limitation

The transaction protects local state within a single service. It does not
coordinate across services — if the flight booking succeeds but the hotel
reservation fails, the flight booking is not rolled back. That cross-service
problem requires a saga or compensation mechanism (Category B).