# Pessimistic locking for inventory reservations

## Category

A2 - Concurrency control.

## Problem

The original booking flow checked the available inventory and then updated it without locking the database row. If several requests arrived at the same time, they could all read the same availability before any request completed its update. For example, multiple requests could each see one remaining seat, pass the availability check, and attempt to reserve it. This race condition could cause overbooking or allow the available inventory to become negative.

## Invariant or guarantee

The available seat or room count must never fall below zero. When concurrent requests compete for the final unit of inventory, only one request may succeed; the remaining requests must receive a conflict response.

## Modified files

- `flight_service/main.py`
- `hotel_service/main.py`
- `scripts/demo_pessimistic_locking.py`

## Behavior before

Concurrent requests could read the same inventory value and independently decide that enough inventory was available. Because the check and update were not protected from other transactions, more bookings or reservations could be accepted than the available capacity allowed.

## Behavior after

The flight and hotel services perform the availability check inside a database transaction and retrieve the inventory row using `SELECT ... FOR UPDATE`. This obtains an exclusive row-level lock. A competing transaction attempting to lock the same flight or hotel row must wait until the current transaction commits or rolls back.

The first request checks the inventory, decrements it, creates the booking or reservation, and commits. A waiting request then locks and reads the newly updated row. If no inventory remains, it returns HTTP `409 Conflict` instead of decrementing the value again. Requests for different inventory rows can still proceed concurrently because the lock applies only to the selected row.

The surrounding transaction is important because it holds the lock and makes the inventory update and booking or reservation insert succeed or fail together.

## How to test

Start the services:

```bash
docker compose up --build -d
```

Run the concurrency demonstration:

```bash
docker compose run --rm tools python scripts/demo_pessimistic_locking.py
```

The script sends 20 concurrent requests for a flight with one remaining seat and 20 concurrent requests for a hotel with one remaining room. For each resource, the expected result is one successful request, 19 conflict responses, zero remaining inventory, and exactly one confirmed booking or reservation.

## Limitation

Pessimistic locking trades concurrency for correctness. Requests targeting the same row are serialized and may spend time waiting, so a popular flight or hotel can become a performance bottleneck. Transactions that acquire multiple locks in inconsistent orders can also deadlock. The guarantee only applies when all code paths modifying the inventory use the same database and locking protocol; it does not provide a lock across independent services or databases.
