# Client request idempotency key

## Category

C - Communication, consistency, or scaling.

## Problem

The baseline trip service treated every `POST /trips` request as a new operation. If a client retried after a timeout or lost response, the service created another trip and repeated the flight booking, hotel reservation, payment authorization, and notification side effects.

## Invariant or guarantee

Requests using the same idempotency key and the same logical request data start at most one trip workflow and return the same trip. Reusing an idempotency key with different request data returns HTTP 409 Conflict.

## Modified files

- `trip_service/main.py`
- `trip_service/db.py`
- `scripts/common.py`
- `scripts/demo_duplicate_request.py`
- `tests/test_trip_idempotency.py`
- Existing scripts and tests that create trips were updated to provide an idempotency key.

## Behavior before

Submitting the same logical request twice created two trips and repeated all downstream side effects.

## Behavior after

The trip service stores the key, a SHA-256 fingerprint of the logical request, its processing status, and the associated trip ID in PostgreSQL. Claiming a new key, creating the pending trip, and linking the two records happen in one local database transaction. A completed retry returns the existing trip before any downstream calls are made. A key reused for different request data is rejected.

The client supplies the key through the required `Idempotency-Key` HTTP header. The request fingerprint excludes the `simulate` field because those values control demonstrations rather than describe the logical trip being booked.

The stored status defines how later requests behave:

- `PROCESSING`: the original request is still running, so another request with that key receives HTTP 409.
- `COMPLETED`: the service loads and returns the existing trip without repeating downstream calls.
- `FAILED`: the original failure is returned and the workflow is not automatically attempted again.

## Implementation flow

1. FastAPI reads the `Idempotency-Key` header.
2. The trip service creates a SHA-256 fingerprint from the validated request data.
3. PostgreSQL attempts to insert the key using its primary-key uniqueness constraint.
4. For a new key, one transaction stores the key, creates the `PENDING` trip, and links the trip ID to the key.
5. The normal flight, hotel, payment, and notification workflow runs.
6. The idempotency record is marked `COMPLETED` or `FAILED` based on the result.
7. A repeated completed request returns before any remote side effects are called again.

The transaction is important because it guarantees that the key and its trip are saved together. Without it, a crash between separate database operations could leave a key permanently marked `PROCESSING` without an associated trip.

## How to test

```bash
docker compose run --rm tools pytest tests/test_trip_idempotency.py -v
docker compose run --rm tools python scripts/demo_duplicate_request.py
```

The test and demo verify that two submissions with the same key return one trip and create only one flight booking, hotel reservation, and payment authorization. The test also verifies that conflicting key reuse returns HTTP 409.

The complete application test suite can be run with:

```bash
docker compose run --rm tools pytest -v
```

## Trade-off

Persistent idempotency records improve retry safety but consume database storage and add a database lookup or insert to each trip request. Requiring the header also changes the API contract: clients must generate a new unique key for each new logical booking and reuse that key only when retrying that booking.

## Limitation

The mechanism protects retries at the trip-service API boundary. It does not make downstream HTTP operations independently idempotent if the trip service crashes after a remote side effect succeeds but before that result is recorded. Requests already marked `FAILED` are not automatically retried, and stored idempotency records currently have no expiration policy.
