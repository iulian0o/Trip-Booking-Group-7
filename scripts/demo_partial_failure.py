from common import base_trip_payload, create_trip, get_state, pretty, reset_all


def main() -> None:
    reset_all()
    response = create_trip(
        base_trip_payload(payment_force_decline=True),
        idempotency_key="demo-partial-failure-001"
    )

    print("Payment failed after flight and hotel succeeded.")
    print("The trip is FAILED, and compensation cancels the reserved resources.")
    print("Trip response:")
    print(pretty(response.json()))
    print("State:")
    print(pretty(get_state()))


if __name__ == "__main__":
    main()

