
import sys
import httpx
from common import base_trip_payload, create_trip, get_state, pretty, reset_all

FLIGHT_URL = "http://flight-service:8000"
HOTEL_URL  = "http://hotel-service:8000"


def main() -> None:
    print("\nCompensation Path Demo\n")
    reset_all()

    # Check initial inventory ---
    flights_before = httpx.get(f"{FLIGHT_URL}/debug/state").json()
    hotels_before  = httpx.get(f"{HOTEL_URL}/debug/state").json()

    flight_id = flights_before["flights"][0]["id"]
    hotel_id  = hotels_before["hotels"][0]["id"]
    seats_before = flights_before["flights"][0]["seats_available"]
    rooms_before = hotels_before["hotels"][0]["rooms_available"]

    print(f"Seats before booking attempt : {seats_before}")
    print(f"Rooms before booking attempt : {rooms_before}\n")

    # Trigger the failure scenario
    payload = base_trip_payload(payment_force_decline=True)
    response = create_trip(payload, idempotency_key="demo-compensation-001")

    print("Trip response (expected 502):")
    print(pretty(response.json()))
    print()

    flights_after = httpx.get(f"{FLIGHT_URL}/debug/state").json()
    hotels_after  = httpx.get(f"{HOTEL_URL}/debug/state").json()

    seats_after = flights_after["flights"][0]["seats_available"]
    rooms_after  = hotels_after["hotels"][0]["rooms_available"]

    print(f"Seats after compensation : {seats_after}")
    print(f"Rooms after compensation : {rooms_after}\n")

    flight_bookings = flights_after.get("flight_bookings", [])
    hotel_reservations = hotels_after.get("hotel_reservations", [])

    cancelled_flights = [b for b in flight_bookings if b["status"] == "CANCELLED"]
    cancelled_hotels  = [r for r in hotel_reservations if r["status"] == "CANCELLED"]

    print(f"Cancelled flight bookings : {len(cancelled_flights)}")
    print(f"Cancelled hotel reservations : {len(cancelled_hotels)}\n")

    errors = []

    if seats_after != seats_before:
        errors.append(
            f"FAIL: seats were not restored. Before={seats_before}, After={seats_after}"
        )
    else:
        print("PASS: seats restored to original value after compensation.")

    if rooms_after != rooms_before:
        errors.append(
            f"FAIL: rooms were not restored. Before={rooms_before}, After={rooms_after}"
        )
    else:
        print("PASS: rooms restored to original value after compensation.")

    if not cancelled_flights:
        errors.append("FAIL: no flight booking found with status CANCELLED.")
    else:
        print(f"PASS: flight booking status is CANCELLED.")

    if not cancelled_hotels:
        errors.append("FAIL: no hotel reservation found with status CANCELLED.")
    else:
        print(f"PASS: hotel reservation status is CANCELLED.\n")

    if errors:
        for e in errors:
            print(e)
        sys.exit(1)

    print("\nAll checks passed. Compensation path is working correctly.")


if __name__ == "__main__":
    main()
