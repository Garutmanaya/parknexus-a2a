"""
Provider service layer for ParkNexus A2A.

This module contains reusable reservation logic for every provider agent.

It supports:
- slot search
- transaction-safe hold
- confirm reservation
- cancel hold
- release slot
- expire holds

Each provider instance uses this same logic against its own database.
"""

from datetime import timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from agent_runtime.models import (
    Garage,
    ParkingSlot,
    Reservation,
    ReservationStatus,
    SlotEvent,
    SlotHold,
    SlotStatus,
    utc_now,
)

from shared.logging.logger import get_logger

logger = get_logger(__name__)

def search_available_slots(
    db: Session,
    level_name: str | None = None,
    slot_type: str | None = None,
    ev_charger: bool | None = None,
    handicap: bool | None = None,
    max_price_per_hour: Decimal | None = None,
    limit: int = 50,
    budget_amount: Decimal | None = None,
    budget_unit: str | None = None,
    duration_minutes: int | None = None,
) -> list[ParkingSlot]:
    """
    Search available slots in the current provider database.
    """
    query = (
        db.query(ParkingSlot)
        .join(Garage, ParkingSlot.garage_id == Garage.garage_id)
        .filter(ParkingSlot.status == SlotStatus.AVAILABLE)
        .filter(Garage.is_active.is_(True))
    )

    if level_name:
        query = query.filter(ParkingSlot.level_name == level_name)

    if slot_type:
        query = query.filter(ParkingSlot.slot_type == slot_type)

    if ev_charger is not None:
        query = query.filter(ParkingSlot.ev_charger.is_(ev_charger))

    if handicap is not None:
        query = query.filter(ParkingSlot.handicap.is_(handicap))

    if max_price_per_hour is not None:
        query = query.filter(ParkingSlot.price_per_hour <= max_price_per_hour)


    slots = (
        query.order_by(
            ParkingSlot.price_per_hour.asc(),
            ParkingSlot.distance_to_entrance_meters.asc(),
        )
        .limit(limit * 5)
        .all()
    )

    if budget_amount is not None:
        slots = [
            slot for slot in slots
            if calculate_estimated_price(slot, budget_unit, duration_minutes) <= budget_amount
        ]

    return slots[:limit]
    


def get_slot_by_code(db: Session, slot_code: str) -> ParkingSlot | None:
    """
    Return one slot by slot code from current provider database.
    """
    return db.query(ParkingSlot).filter(ParkingSlot.slot_code == slot_code).first()


def hold_slot(
    db: Session,
    slot_code: str,
    user_id: str,
    hold_minutes: int = 5,
) -> SlotHold:
    """
    Transaction-safe slot hold.

    Uses SELECT FOR UPDATE to prevent double booking.
    """
    try:
        slot = (
            db.query(ParkingSlot)
            .filter(ParkingSlot.slot_code == slot_code)
            .with_for_update()
            .first()
        )

        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")

        if slot.status != SlotStatus.AVAILABLE:
            raise HTTPException(
                status_code=409,
                detail=f"Slot is not available. Current status: {slot.status.value}",
            )

        now = utc_now()
        old_status = slot.status

        hold = SlotHold(
            slot_id=slot.slot_id,
            user_id=user_id,
            status=ReservationStatus.HELD,
            expires_at=now + timedelta(minutes=hold_minutes),
        )

        slot.status = SlotStatus.HELD
        slot.updated_at = now

        event = SlotEvent(
            slot_id=slot.slot_id,
            old_status=old_status,
            new_status=SlotStatus.HELD,
            event_type="SLOT_HELD",
            actor_id=user_id,
            reason=f"Slot held for {hold_minutes} minutes",
        )

        db.add(hold)
        db.add(event)
        db.commit()
        db.refresh(hold)

        return hold

    except HTTPException:
        db.rollback()
        raise

    except SQLAlchemyError as exc:
        db.rollback()
        raise RuntimeError(f"Database error while holding slot: {exc}") from exc


def confirm_reservation(
    db: Session,
    hold_id: str,
    user_id: str,
    reserved_minutes: int = 60,
) -> Reservation:
    """
    Confirm an active hold into a reservation.
    """
    try:
        hold = (
            db.query(SlotHold)
            .filter(SlotHold.hold_id == hold_id)
            .with_for_update()
            .first()
        )

        if not hold:
            raise HTTPException(status_code=404, detail="Hold not found")

        if hold.user_id != user_id:
            raise HTTPException(status_code=403, detail="Hold does not belong to user")

        if hold.status != ReservationStatus.HELD:
            raise HTTPException(
                status_code=409,
                detail=f"Hold is not active. Current status: {hold.status.value}",
            )

        now = utc_now()

        if hold.expires_at <= now:
            raise HTTPException(status_code=409, detail="Hold has expired")

        slot = (
            db.query(ParkingSlot)
            .filter(ParkingSlot.slot_id == hold.slot_id)
            .with_for_update()
            .first()
        )

        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")

        if slot.status != SlotStatus.HELD:
            raise HTTPException(
                status_code=409,
                detail=f"Slot is not held. Current status: {slot.status.value}",
            )

        old_status = slot.status
        reserved_from = now
        reserved_until = now + timedelta(minutes=reserved_minutes)

        total_price = Decimal(slot.price_per_hour) * (
            Decimal(reserved_minutes) / Decimal(60)
        )

        reservation = Reservation(
            slot_id=slot.slot_id,
            hold_id=hold.hold_id,
            user_id=user_id,
            status=ReservationStatus.CONFIRMED,
            reserved_from=reserved_from,
            reserved_until=reserved_until,
            total_price=total_price,
        )

        hold.status = ReservationStatus.CONFIRMED
        hold.updated_at = now

        slot.status = SlotStatus.RESERVED
        slot.updated_at = now

        event = SlotEvent(
            slot_id=slot.slot_id,
            old_status=old_status,
            new_status=SlotStatus.RESERVED,
            event_type="RESERVATION_CONFIRMED",
            actor_id=user_id,
            reason=f"Reservation confirmed for {reserved_minutes} minutes",
        )

        db.add(reservation)
        db.add(event)
        db.commit()
        db.refresh(reservation)

        return reservation

    except HTTPException:
        db.rollback()
        raise

    except SQLAlchemyError as exc:
        db.rollback()
        raise RuntimeError(f"Database error while confirming reservation: {exc}") from exc


def cancel_hold(
    db: Session,
    hold_id: str,
    user_id: str,
) -> ParkingSlot:
    """
    Cancel active hold and return slot to AVAILABLE.
    """
    try:
        hold = (
            db.query(SlotHold)
            .filter(SlotHold.hold_id == hold_id)
            .with_for_update()
            .first()
        )

        if not hold:
            raise HTTPException(status_code=404, detail="Hold not found")

        if hold.user_id != user_id:
            raise HTTPException(status_code=403, detail="Hold does not belong to user")

        if hold.status != ReservationStatus.HELD:
            raise HTTPException(
                status_code=409,
                detail=f"Hold is not active. Current status: {hold.status.value}",
            )

        slot = (
            db.query(ParkingSlot)
            .filter(ParkingSlot.slot_id == hold.slot_id)
            .with_for_update()
            .first()
        )

        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")

        now = utc_now()
        old_status = slot.status

        hold.status = ReservationStatus.CANCELLED
        hold.updated_at = now

        slot.status = SlotStatus.AVAILABLE
        slot.updated_at = now

        event = SlotEvent(
            slot_id=slot.slot_id,
            old_status=old_status,
            new_status=SlotStatus.AVAILABLE,
            event_type="HOLD_CANCELLED",
            actor_id=user_id,
            reason="User cancelled hold",
        )

        db.add(event)
        db.commit()
        db.refresh(slot)

        return slot

    except HTTPException:
        db.rollback()
        raise

    except SQLAlchemyError as exc:
        db.rollback()
        raise RuntimeError(f"Database error while cancelling hold: {exc}") from exc


def release_slot(
    db: Session,
    slot_code: str,
    user_id: str,
    reason: str | None = None,
) -> ParkingSlot:
    """
    Release HELD, RESERVED, or OCCUPIED slot back to AVAILABLE.
    """
    try:
        slot = (
            db.query(ParkingSlot)
            .filter(ParkingSlot.slot_code == slot_code)
            .with_for_update()
            .first()
        )

        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")

        if slot.status == SlotStatus.AVAILABLE:
            raise HTTPException(status_code=409, detail="Slot is already available")

        now = utc_now()
        old_status = slot.status

        slot.status = SlotStatus.AVAILABLE
        slot.updated_at = now

        event = SlotEvent(
            slot_id=slot.slot_id,
            old_status=old_status,
            new_status=SlotStatus.AVAILABLE,
            event_type="SLOT_RELEASED",
            actor_id=user_id,
            reason=reason or "Slot manually released",
        )

        db.add(event)
        db.commit()
        db.refresh(slot)

        return slot

    except HTTPException:
        db.rollback()
        raise

    except SQLAlchemyError as exc:
        db.rollback()
        raise RuntimeError(f"Database error while releasing slot: {exc}") from exc


def expire_holds(db: Session) -> int:
    """
    Expire all active holds whose expiration timestamp has passed.
    """
    try:
        now = utc_now()

        expired_holds = (
            db.query(SlotHold)
            .filter(SlotHold.status == ReservationStatus.HELD)
            .filter(SlotHold.expires_at <= now)
            .with_for_update()
            .all()
        )

        expired_count = 0

        for hold in expired_holds:
            slot = (
                db.query(ParkingSlot)
                .filter(ParkingSlot.slot_id == hold.slot_id)
                .with_for_update()
                .first()
            )

            if not slot:
                continue

            old_status = slot.status

            hold.status = ReservationStatus.EXPIRED
            hold.updated_at = now

            slot.status = SlotStatus.AVAILABLE
            slot.updated_at = now

            event = SlotEvent(
                slot_id=slot.slot_id,
                old_status=old_status,
                new_status=SlotStatus.AVAILABLE,
                event_type="HOLD_EXPIRED",
                actor_id="system",
                reason="Hold expired automatically",
            )

            db.add(event)
            expired_count += 1

        db.commit()

        return expired_count

    except SQLAlchemyError as exc:
        db.rollback()
        raise RuntimeError(f"Database error while expiring holds: {exc}") from exc

def calculate_estimated_price(
    slot: ParkingSlot,
    budget_unit: str | None = None,
    duration_minutes: int | None = None,
) -> Decimal:
    """
    Calculate estimated price using provider-owned pricing rules.
    """
    unit = budget_unit or "hour"

    if unit == "day":
        if slot.daily_rate is not None:
            return Decimal(slot.daily_rate)
        return Decimal(slot.price_per_hour) * Decimal(24)

    if unit == "month":
        if slot.monthly_rate is not None:
            return Decimal(slot.monthly_rate)
        return Decimal(slot.price_per_hour) * Decimal(24 * 30)

    if unit == "total" and duration_minutes:
        hours = Decimal(duration_minutes) / Decimal(60)
        return Decimal(slot.price_per_hour) * hours

    if duration_minutes:
        hours = Decimal(duration_minutes) / Decimal(60)
        return Decimal(slot.price_per_hour) * hours

    return Decimal(slot.price_per_hour)

if __name__ == "__main__":
    """
    Manual test:
        python -m agent_runtime.service --config agents/company_a/agent.yaml
    """
    import argparse

    from agent_runtime.config_loader import load_agent_config
    from agent_runtime.database import create_provider_engine, create_session_factory
    from agent_runtime.seed import seed_provider_database

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to provider agent.yaml")
    args = parser.parse_args()

    config = load_agent_config(args.config)

    seed_provider_database(config)

    engine = create_provider_engine(config)
    SessionLocal = create_session_factory(engine)
    db = SessionLocal()

    try:
        slots = search_available_slots(db, level_name="GROUND", limit=3)
        print(f"Available slots found: {len(slots)}")

        for slot in slots:
            print(slot.slot_code, slot.status.value, slot.price_per_hour)

        if slots:
            test_slot = slots[0]
            hold = hold_slot(
                db=db,
                slot_code=test_slot.slot_code,
                user_id="manual_test_user",
                hold_minutes=1,
            )
            print(f"Held slot: {test_slot.slot_code}")
            print(f"hold_id={hold.hold_id}")

    finally:
        db.close()
