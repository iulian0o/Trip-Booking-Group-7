from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx

from common import FLIGHT_URL, HOTEL_URL, pretty, reset_all


async def book_flight(client: httpx.AsyncClient) -> httpx.Response:
    return await client.post(
        f"{FLIGHT_URL}/flights/FL-ONE-SEAT/bookings",
        json={
            "trip_id": str(uuid4()),
            "traveler_name": "Pessimistic Locking Student",
            "seats": 1,
            "delay_after_check_ms": 200,
            "fail_after_decrement": False,
        },
    )


async def reserve_hotel(client: httpx.AsyncClient) -> httpx.Response:
    return await client.post(
        f"{HOTEL_URL}/hotels/HT-ONE-ROOM/reservations",
        json={
            "trip_id": str(uuid4()),
            "traveler_name": "Pessimistic Locking Student",
            "nights": 1,
            "rooms": 1,
            "delay_after_check_ms": 200,
            "force_fail": False,
        },
    )


async def run_race(url: str, request_fn) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        responses = await asyncio.gather(*[request_fn(client) for _ in range(20)])
        success = [r for r in responses if r.status_code == 200]
        conflict = [r for r in responses if r.status_code == 409]
        error = [r for r in responses if r.status_code not in (200, 409)]

        print(f"Requests: {len(responses)}")
        print(f"Successful: {len(success)}")
        print(f"Conflicts: {len(conflict)}")
        print(f"Other errors: {len(error)}")

        if url == FLIGHT_URL:
            state = (await client.get(f"{FLIGHT_URL}/debug/state")).json()
            print("Flight state:")
        else:
            state = (await client.get(f"{HOTEL_URL}/debug/state")).json()
            print("Hotel state:")
        print(pretty(state))


async def main() -> None:
    print("Testing flight pessimistic locking...")
    await run_race(FLIGHT_URL, book_flight)
    print("\nTesting hotel pessimistic locking...")
    await run_race(HOTEL_URL, reserve_hotel)


def sync_main() -> None:
    reset_all()
    asyncio.run(main())


if __name__ == "__main__":
    sync_main()
