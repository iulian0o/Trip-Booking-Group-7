# Compensation path for a distributed operation

# Category: B

## Problem
In the baseline application, the booking flow calls flight-service, then hotel-service,
then payment-service in sequence. If payment fails, the flight booking and hotel reservation
remain in CONFIRMED status inside their services.

Those resources seat and room, are permanently leaked. The trip is marked FAILED but the
extrernal services have no knowledge of the failure.

## Invariant or guarantee
If any step in the booking sequence fails, every step that previously succeded must be reversed.
After compensation, the flight booking and hotel reservation must be CANCELLED and the
corresponding inventory (seats and room) must be restored to the value it had before the attempt.

## Behavior before
Payment fails → trip status = FAILED, but flight booking status =
CONFIRMED, hotel reservation status = CONFIRMED, seats and rooms
permanently decremented. The resources can never be used by another trip.

## Behavior after
Payment fails → _compensate() is called with the IDs of the resources
that were successfully created. Hotel reservation is cancelled first
(reverse order), then flight booking. Both services restore their
inventory. The trip error_message records both the original failure
and the outcome of each compensation step.

## How to test
```bash
docker compose up --build -d
docker compose run --rm tools python scripts/demo_compensation.py
```
The script asserts that seat and room counts are identical before and
after the failed booking attempt, and that booking records show status
CANCELLED.

## Limitation
- Compensation itself can fail (ex: a service is temporarily down).
  The current implementation logs the failure but does not retry.
  A production system would persist pending compensation steps and
  retry them asynchronously (durable saga state machine).
- There is no payment compensation. The payment service records a
  DECLINED status internally, so no explicit cancel call is needed
  for a declined payment. A force_error case (server crash mid-payment)
  is not compensated because we cannot know whether the charge was
  applied.
- This is not TCC, resources are fully reserved
  during the forward path, not tentatively held. A true TCC would
  require a separate "hold" state in flight-service and hotel-service.