"""
Demo: database transaction prevents partial state on forced failure.

The flight booking endpoint has a fail_after_decrement flag that crashes
the service after decrementing seats but before inserting the booking row.

Without a transaction, this would leave seats decremented with no booking.
With a transaction, the entire operation is rolled back.

Run with:
docker compose run --rm tools python scripts/demo_transaction.py
"""
from common import FLIGHT_URL, pretty, reset_all
import httpx
from uuid import uuid4


def main() -> None:
    reset_all()

    with httpx.Client(timeout=10) as client:
        before = client.get(f"{FLIGHT_URL}/debug/state").json()
        seats_before = next(f for f in before["flights"] if f["id"] == "FL-ONE-SEAT")["seats_available"]
        print(f"Seats before forced failure: {seats_before}")

        response = client.post(
            f"{FLIGHT_URL}/flights/FL-ONE-SEAT/bookings",
            json={
                "trip_id": str(uuid4()),
                "traveler_name": "Test Traveler",
                "seats": 1,
                "delay_after_check_ms": 0,
                "fail_after_decrement": True,
            },
        )
        print(f"Response status: {response.status_code} (expected 500)")

        after = client.get(f"{FLIGHT_URL}/debug/state").json()
        seats_after = next(f for f in after["flights"] if f["id"] == "FL-ONE-SEAT")["seats_available"]
        print(f"Seats after forced failure: {seats_after}")

        if seats_after == seats_before:
            print("OK: transaction rolled back — seats unchanged despite forced crash.")
        else:
            print("FAIL: seats were decremented without a booking — partial state!")

        print("\nFull state:")
        print(pretty(after))


if __name__ == "__main__":
    main()