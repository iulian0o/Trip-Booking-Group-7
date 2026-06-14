import sys
from common import base_trip_payload, create_trip, pretty, reset_all, wait_for_notifications


def main() -> None:
    print("\nDuplicate Message Handling Demo\n")
    reset_all()

    payload = base_trip_payload(publish_event_twice=True)
    response = create_trip(payload)
    response.raise_for_status()
    trip = response.json()
    trip_id = trip["id"]

    print(f"Trip confirmed: {trip_id}")
    print("Event published TWICE with the same event_id.\n")

    notifications = wait_for_notifications(trip_id, minimum=1, timeout_seconds=5)

    print(f"Notifications stored in database: {len(notifications)}")
    print(pretty(notifications))
    print()

    if len(notifications) == 1:
        print("PASS: exactly 1 notification stored despite 2 message deliveries.")
        print("PASS: duplicate message was detected and skipped.")
    elif len(notifications) == 0:
        print("FAIL: no notification stored at all — worker may not be running.")
        sys.exit(1)
    else:
        print(f"FAIL: {len(notifications)} notifications stored — deduplication is NOT working.")
        sys.exit(1)

if __name__ == "__main__":
    main()

