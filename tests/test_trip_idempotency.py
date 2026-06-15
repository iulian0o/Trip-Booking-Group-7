from __future__ import annotations

import asyncio
import os

import httpx

from shared.rabbitmq import purge_notification_queue

TRIP_URL = os.getenv("TRIP_URL", "http://localhost:8000")
FLIGHT_URL = os.getenv("FLIGHT_URL", "http://localhost:8001")
HOTEL_URL = os.getenv("HOTEL_URL", "http://localhost:8002")
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://localhost:8003")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://localhost:8004")


def reset_all() -> None:
    asyncio.run(purge_notification_queue())
    with httpx.Client(timeout=10) as client:
        for base_url in [TRIP_URL, FLIGHT_URL, HOTEL_URL, PAYMENT_URL, NOTIFICATION_URL]:
            client.post(f"{base_url}/admin/reset").raise_for_status()


def trip_payload() -> dict:
    return {
        "user_id": "user-1",
        "traveler_name": "Ada Lovelace",
        "flight_id": "FL-MANY-SEATS",
        "hotel_id": "HT-MANY-ROOMS",
        "nights": 2,
        "simulate": {},
    }


def test_same_key_returns_same_trip_without_duplicate_side_effects() -> None:
    reset_all()
    headers = {"Idempotency-Key": "test-create-trip-001"}

    with httpx.Client(timeout=15) as client:
        first = client.post(f"{TRIP_URL}/trips", json=trip_payload(), headers=headers)
        second = client.post(f"{TRIP_URL}/trips", json=trip_payload(), headers=headers)
        trips = client.get(f"{TRIP_URL}/trips").json()
        flight_state = client.get(f"{FLIGHT_URL}/debug/state").json()
        hotel_state = client.get(f"{HOTEL_URL}/debug/state").json()
        payment_state = client.get(f"{PAYMENT_URL}/debug/state").json()

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert len(trips) == 1
    assert len(flight_state["flight_bookings"]) == 1
    assert len(hotel_state["hotel_reservations"]) == 1
    assert len(payment_state["payment_authorizations"]) == 1


def test_same_key_with_different_payload_is_rejected() -> None:
    reset_all()
    headers = {"Idempotency-Key": "test-create-trip-conflict-001"}
    changed_payload = trip_payload()
    changed_payload["nights"] = 3

    with httpx.Client(timeout=15) as client:
        first = client.post(f"{TRIP_URL}/trips", json=trip_payload(), headers=headers)
        conflicting_retry = client.post(
            f"{TRIP_URL}/trips",
            json=changed_payload,
            headers=headers,
        )
        trips = client.get(f"{TRIP_URL}/trips").json()

    assert first.status_code == 200
    assert conflicting_retry.status_code == 409
    assert len(trips) == 1
