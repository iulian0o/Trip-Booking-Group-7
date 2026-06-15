from common import base_trip_payload, create_trip, get_state, pretty, reset_all


def main() -> None:
    reset_all()
    payload = base_trip_payload()
    idempotency_key = "demo-create-trip-001"

    first = create_trip(payload, idempotency_key=idempotency_key)
    second = create_trip(payload, idempotency_key=idempotency_key)

    print("Same logical user action submitted twice with one Idempotency-Key.")
    print("Expected after Part C: both responses identify the same trip.")
    print("First response:")
    print(pretty(first.json()))
    print("Second response:")
    print(pretty(second.json()))
    print("State:")
    print(pretty(get_state()))

    first.raise_for_status()
    second.raise_for_status()
    assert first.json()["id"] == second.json()["id"]


if __name__ == "__main__":
    main()

