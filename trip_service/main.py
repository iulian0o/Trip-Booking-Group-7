from __future__ import annotations

import hashlib
import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Header

from shared.logging import configure_logging
from trip_service import clients, db, events
from trip_service.pricing import calculate_amount_cents
from trip_service.schemas import CreateTripRequest

SERVICE_NAME = "trip-service"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(SERVICE_NAME)
    await db.connect_with_retry()
    await db.init_db()
    yield
    await db.close()


app = FastAPI(title="Trip Service", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.post("/admin/reset")
async def reset() -> dict[str, str]:
    await db.reset_db()
    return {"status": "ok"}


@app.get("/debug/state")
async def debug_state() -> dict:
    return await db.state()


@app.get("/trips")
async def list_trips() -> list[dict]:
    return (await db.state())["trips"]


@app.get("/trips/{trip_id}")
async def get_trip(trip_id: UUID) -> dict:
    trip = await db.get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@app.post("/trips")
async def create_trip(
    request: CreateTripRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict:
    
    request_json = request.model_dump_json(exclude={"simulate"})

    request_hash = hashlib.sha256(
        request_json.encode("utf-8")
    ).hexdigest()

    trip = await db.claim_key_and_create_trip(
        key=idempotency_key,
        request_hash=request_hash,
        user_id=request.user_id,
        traveler_name=request.traveler_name,
        flight_id=request.flight_id,
        hotel_id=request.hotel_id,
        nights=request.nights,
    )

    if trip is None:
        existing_key = await db.get_idempotency_key(idempotency_key)

        if existing_key is None:
            raise HTTPException(
                status_code=500,
                detail="Idempotency record could not be loaded",
            )

        if existing_key["request_hash"] != request_hash:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key was already used for a different request",
            )

        if existing_key["status"] == "COMPLETED":
            existing_trip = await db.get_trip(existing_key["trip_id"])

            if existing_trip is None:
                raise HTTPException(
                    status_code=500,
                    detail="Trip linked to idempotency key was not found",
                )

            return existing_trip
        
        if existing_key["status"] == "FAILED":
            existing_trip = await db.get_trip(existing_key["trip_id"])

            if existing_trip is None:
                raise HTTPException(
                    status_code=500,
                    detail="Trip linked to idempotency key was not found",
                )

            raise HTTPException(
                status_code=409,
                detail={
                    "message": "The original request failed and will not be retried",
                    "trip_id": str(existing_trip["id"]),
                    "error": existing_trip["error_message"],
                },
            )

        raise HTTPException(
            status_code=409,
            detail="This request is already being processed",
        )

    trip_id = trip["id"]

    try:
        flight_booking = await clients.book_flight(
            flight_id=request.flight_id,
            trip_id=str(trip_id),
            traveler_name=request.traveler_name,
            delay_after_check_ms=request.simulate.flight_delay_after_check_ms,
        )
        trip = await db.update_trip(trip_id, flight_booking_id=UUID(flight_booking["id"]))

        hotel_reservation = await clients.reserve_hotel(
            hotel_id=request.hotel_id,
            trip_id=str(trip_id),
            traveler_name=request.traveler_name,
            nights=request.nights,
            delay_after_check_ms=request.simulate.hotel_delay_after_check_ms,
            force_fail=request.simulate.hotel_force_fail,
        )
        trip = await db.update_trip(trip_id, hotel_reservation_id=UUID(hotel_reservation["id"]))

        flight = await clients.get_flight(request.flight_id)
        hotel = await clients.get_hotel(request.hotel_id)
        amount_cents = calculate_amount_cents(
            flight_price_cents=flight["price_cents"],
            hotel_price_per_night_cents=hotel["price_per_night_cents"],
            nights=request.nights,
        )
        trip = await db.update_trip(trip_id, amount_cents=amount_cents)

        payment = await clients.authorize_payment(
            trip_id=str(trip_id),
            amount_cents=amount_cents,
            force_decline=request.simulate.payment_force_decline,
            force_error=request.simulate.payment_force_error,
            delay_ms=request.simulate.payment_delay_ms,
        )
        trip = await db.update_trip(
            trip_id,
            payment_authorization_id=UUID(payment["id"]),
            status="CONFIRMED",
            error_message=None,
        )

    except Exception as exc:
        failed = await db.update_trip(
            trip_id,
            status="FAILED",
            error_message=str(exc),
        )

        await db.update_idempotency_status(
            key=idempotency_key,
            status="FAILED",
        )

        raise HTTPException(
            status_code=502,
            detail={
                "trip_id": str(trip_id),
                "error": failed["error_message"],
            },
        )

    try:
        await events.publish_confirmation(trip, publish_twice=request.simulate.publish_event_twice)
    except Exception:
        # INTENTIONAL NAIVE DESIGN:
        # The trip is already confirmed. There is no transactional outbox to
        # guarantee that the notification event will eventually be published.
        logging.exception("Failed to publish trip.confirmed event")

    await db.update_idempotency_status(
        key=idempotency_key,
        status="COMPLETED",
    )

    return trip