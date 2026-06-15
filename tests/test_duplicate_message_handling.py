from __future__ import annotations

import asyncio
import os
import time

import httpx

from shared.rabbitmq import purge_notification_queue

TRIP_URL = os.getenv("TRIP_URL", "http://localhost:8000")
FLIGHT_URL = os.getenv("FLIGHT_URL", "http://localhost:8001")
HOTEL_URL = os.getenv("HOTEL_URL", "http://localhost:8002")
PAYMENT_URL = os.getenv("PAYMENT_URL", "http://localhost:8003")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://localhost:8004")
SERVICE_URLS = [TRIP_URL, FLIGHT_URL, HOTEL_URL, PAYMENT_URL, NOTIFICATION_URL]


def reset_all() -> None:
    asyncio.run(purge_notification_queue())
    with httpx.Client(timeout=10) as client:
        for base_url in SERVICE_URLS:
            client.post(f"{base_url}/admin/reset").raise_for_status()


def wait_for_notifications(trip_id: str) -> list[dict]:
    deadline = time.monotonic() + 8
    with httpx.Client(timeout=10) as client:
        while time.monotonic() < deadline:
            notifications = client.get(
                f"{NOTIFICATION_URL}/notifications/{trip_id}"
            ).json()
            if notifications:
                time.sleep(0.5)
                return client.get(
                    f"{NOTIFICATION_URL}/notifications/{trip_id}"
                ).json()
            time.sleep(0.2)

        return client.get(
            f"{NOTIFICATION_URL}/notifications/{trip_id}"
        ).json()


def test_duplicate_event_is_stored_once() -> None:
    reset_all()

    with httpx.Client(timeout=15) as client:
        response = client.post(
            f"{TRIP_URL}/trips",
            headers={"Idempotency-Key": "test-duplicate-message-001"},
            json={
                "user_id": "user-1",
                "traveler_name": "Ada Lovelace",
                "flight_id": "FL-MANY-SEATS",
                "hotel_id": "HT-MANY-ROOMS",
                "nights": 2,
                "simulate": {"publish_event_twice": True},
            },
        )

    assert response.status_code == 200

    notifications = wait_for_notifications(response.json()["id"])

    assert len(notifications) == 1
    assert notifications[0]["trip_id"] == response.json()["id"]
