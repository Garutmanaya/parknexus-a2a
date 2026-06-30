"""Provider service layer for ParkNexus A2A."""

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


def calculate_estimated_price(slot: ParkingSlot, budget_unit: str | None = None, duration_minutes: int | None = None) -> Decimal:
    unit = (budget_unit or "hour").lower()
    if unit == "day":
        return Decimal(slot.daily_rate) if slot.daily_rate is not None else Decimal(slot.hourly_rate) * Decimal(24)
    if unit == "month":
        return Decimal(slot.monthly_rate) if slot.monthly_rate is not None else Decimal(slot.hourly_rate) * Decimal(24 * 30)
    if unit == "total" and duration_minutes:
        return Decimal(slot.hourly_rate) * (Decimal(duration_minutes) / Decimal(60))
    if duration_minutes:
        return Decimal(slot.hourly_rate) * (Decimal(duration_minutes) / Decimal(60))
    return Decimal(slot.hourly_rate)


def search_available_slots(
    db: Session,
    level_name: str | None = None,
    slot_type: str | None = None,
    ev_charger: bool | None = None,
    handicap: bool | None = None,
    max_hourly_rate: Decimal | None = None,
    limit: int = 50,
    budget_amount: Decimal | None = None,
    budget_unit: str | None = None,
    duration_minutes: int | None = None,
) -> list[ParkingSlot]:
    logger.info("slot_search_started")
    logger.debug(
        "slot_search_params level_name=%s slot_type=%s ev_charger=%s handicap=%s max_hourly_rate=%s budget_amount=%s budget_unit=%s duration_minutes=%s limit=%s",
        level_name, slot_type, ev_charger, handicap, max_hourly_rate, budget_amount, budget_unit, duration_minutes, limit,
    )
    query = db.query(ParkingSlot).join(Garage, ParkingSlot.garage_id == Garage.garage_id).filter(
        ParkingSlot.status == SlotStatus.AVAILABLE,
        Garage.is_active.is_(True),
    )
    if level_name:
        query = query.filter(ParkingSlot.level_name == level_name)
    if slot_type:
        query = query.filter(ParkingSlot.slot_type == slot_type)
    if ev_charger is not None:
        query = query.filter(ParkingSlot.ev_charger.is_(ev_charger))
    if handicap is not None:
        query = query.filter(ParkingSlot.handicap.is_(handicap))
    if max_hourly_rate is not None:
        query = query.filter(ParkingSlot.hourly_rate <= max_hourly_rate)
    if budget_amount is not None and (budget_unit or "hour").lower() == "hour" and duration_minutes is None:
        query = query.filter(ParkingSlot.hourly_rate <= budget_amount)

    slots = query.order_by(ParkingSlot.hourly_rate.asc(), ParkingSlot.distance_to_entrance_meters.asc()).limit(limit * 10).all()
    if budget_amount is not None:
        slots = [slot for slot in slots if calculate_estimated_price(slot, budget_unit, duration_minutes) <= budget_amount]
    result = slots[:limit]
    logger.info("slot_search_completed count=%s", len(result))
    return result


def get_slot_by_code(db: Session, slot_code: str) -> ParkingSlot | None:
    return db.query(ParkingSlot).filter(ParkingSlot.slot_code == slot_code).first()


def get_garage_layout(db: Session) -> dict:
    """Return garage layout suitable for the visual console UI."""
    garages = db.query(Garage).filter(Garage.is_active.is_(True)).all()
    result = []
    for garage in garages:
        slots = db.query(ParkingSlot).filter(ParkingSlot.garage_id == garage.garage_id).order_by(
            ParkingSlot.level_name, ParkingSlot.row_label, ParkingSlot.column_number
        ).all()
        levels: dict[str, dict] = {}
        for slot in slots:
            level = levels.setdefault(slot.level_name, {"name": slot.level_name, "rows": {}})
            row = level["rows"].setdefault(slot.row_label, [])
            row.append({
                "slot_id": slot.slot_id,
                "slot_code": slot.slot_code,
                "level_name": slot.level_name,
                "row_label": slot.row_label,
                "column_number": slot.column_number,
                "slot_type": slot.slot_type.value,
                "status": slot.status.value,
                "hourly_rate": str(slot.hourly_rate),
                "daily_rate": str(slot.daily_rate) if slot.daily_rate is not None else None,
                "monthly_rate": str(slot.monthly_rate) if slot.monthly_rate is not None else None,
                "distance_to_entrance_meters": slot.distance_to_entrance_meters,
                "ev_charger": slot.ev_charger,
                "handicap": slot.handicap,
            })
        normalized_levels = []
        for level in levels.values():
            normalized_levels.append({
                "name": level["name"],
                "rows": [{"label": label, "slots": row_slots} for label, row_slots in sorted(level["rows"].items())],
            })
        result.append({
            "garage_id": garage.garage_id,
            "name": garage.name,
            "address": garage.address,
            "city": garage.city,
            "state": garage.state,
            "postal_code": garage.postal_code,
            "levels": normalized_levels,
        })
    return {"garages": result}


def hold_slot(db: Session, slot_code: str, user_id: str, hold_minutes: int = 5) -> SlotHold:
    logger.info("slot_hold_started slot_code=%s user_id=%s", slot_code, user_id)
    try:
        slot = db.query(ParkingSlot).filter(ParkingSlot.slot_code == slot_code).with_for_update().first()
        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")
        if slot.status != SlotStatus.AVAILABLE:
            raise HTTPException(status_code=409, detail=f"Slot is not available. Current status: {slot.status.value}")
        now = utc_now()
        old_status = slot.status
        hold = SlotHold(slot_id=slot.slot_id, user_id=user_id, status=ReservationStatus.HELD, expires_at=now + timedelta(minutes=hold_minutes))
        slot.status = SlotStatus.HELD
        slot.updated_at = now
        db.add(hold)
        db.add(SlotEvent(slot_id=slot.slot_id, old_status=old_status, new_status=SlotStatus.HELD, event_type="SLOT_HELD", actor_id=user_id, reason=f"Slot held for {hold_minutes} minutes"))
        db.commit(); db.refresh(hold)
        logger.info("slot_hold_completed slot_code=%s hold_id=%s", slot_code, hold.hold_id)
        return hold
    except HTTPException:
        db.rollback(); raise
    except SQLAlchemyError as exc:
        db.rollback(); logger.error("slot_hold_failed slot_code=%s", slot_code, exc_info=True); raise RuntimeError(f"Database error while holding slot: {exc}") from exc


def confirm_reservation(db: Session, hold_id: str, user_id: str, reserved_minutes: int = 60) -> Reservation:
    logger.info("reservation_confirm_started hold_id=%s user_id=%s", hold_id, user_id)
    try:
        hold = db.query(SlotHold).filter(SlotHold.hold_id == hold_id).with_for_update().first()
        if not hold:
            raise HTTPException(status_code=404, detail="Hold not found")
        if hold.user_id != user_id:
            raise HTTPException(status_code=403, detail="Hold does not belong to user")
        if hold.status != ReservationStatus.HELD:
            raise HTTPException(status_code=409, detail=f"Hold is not active. Current status: {hold.status.value}")
        now = utc_now()
        if hold.expires_at <= now:
            raise HTTPException(status_code=409, detail="Hold has expired")
        slot = db.query(ParkingSlot).filter(ParkingSlot.slot_id == hold.slot_id).with_for_update().first()
        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")
        if slot.status != SlotStatus.HELD:
            raise HTTPException(status_code=409, detail=f"Slot is not held. Current status: {slot.status.value}")
        old_status = slot.status
        reservation = Reservation(
            slot_id=slot.slot_id,
            hold_id=hold.hold_id,
            user_id=user_id,
            status=ReservationStatus.CONFIRMED,
            reserved_from=now,
            reserved_until=now + timedelta(minutes=reserved_minutes),
            total_price=calculate_estimated_price(slot, "total", reserved_minutes),
        )
        hold.status = ReservationStatus.CONFIRMED; hold.updated_at = now
        slot.status = SlotStatus.RESERVED; slot.updated_at = now
        db.add(reservation)
        db.add(SlotEvent(slot_id=slot.slot_id, old_status=old_status, new_status=SlotStatus.RESERVED, event_type="RESERVATION_CONFIRMED", actor_id=user_id, reason=f"Reservation confirmed for {reserved_minutes} minutes"))
        db.commit(); db.refresh(reservation)
        logger.info("reservation_confirm_completed hold_id=%s reservation_id=%s", hold_id, reservation.reservation_id)
        return reservation
    except HTTPException:
        db.rollback(); raise
    except SQLAlchemyError as exc:
        db.rollback(); logger.error("reservation_confirm_failed hold_id=%s", hold_id, exc_info=True); raise RuntimeError(f"Database error while confirming reservation: {exc}") from exc


def cancel_hold(db: Session, hold_id: str, user_id: str) -> ParkingSlot:
    logger.info("hold_cancel_started hold_id=%s user_id=%s", hold_id, user_id)
    try:
        hold = db.query(SlotHold).filter(SlotHold.hold_id == hold_id).with_for_update().first()
        if not hold:
            raise HTTPException(status_code=404, detail="Hold not found")
        if hold.user_id != user_id:
            raise HTTPException(status_code=403, detail="Hold does not belong to user")
        if hold.status != ReservationStatus.HELD:
            raise HTTPException(status_code=409, detail=f"Hold is not active. Current status: {hold.status.value}")
        slot = db.query(ParkingSlot).filter(ParkingSlot.slot_id == hold.slot_id).with_for_update().first()
        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")
        now = utc_now(); old_status = slot.status
        hold.status = ReservationStatus.CANCELLED; hold.updated_at = now
        slot.status = SlotStatus.AVAILABLE; slot.updated_at = now
        db.add(SlotEvent(slot_id=slot.slot_id, old_status=old_status, new_status=SlotStatus.AVAILABLE, event_type="HOLD_CANCELLED", actor_id=user_id, reason="User cancelled hold"))
        db.commit(); db.refresh(slot)
        logger.info("hold_cancel_completed hold_id=%s slot_code=%s", hold_id, slot.slot_code)
        return slot
    except HTTPException:
        db.rollback(); raise
    except SQLAlchemyError as exc:
        db.rollback(); logger.error("hold_cancel_failed hold_id=%s", hold_id, exc_info=True); raise RuntimeError(f"Database error while cancelling hold: {exc}") from exc


def release_slot(db: Session, slot_code: str, user_id: str, reason: str | None = None) -> ParkingSlot:
    logger.info("slot_release_started slot_code=%s user_id=%s", slot_code, user_id)
    try:
        slot = db.query(ParkingSlot).filter(ParkingSlot.slot_code == slot_code).with_for_update().first()
        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")
        if slot.status == SlotStatus.AVAILABLE:
            raise HTTPException(status_code=409, detail="Slot is already available")
        now = utc_now(); old_status = slot.status
        slot.status = SlotStatus.AVAILABLE; slot.updated_at = now
        db.add(SlotEvent(slot_id=slot.slot_id, old_status=old_status, new_status=SlotStatus.AVAILABLE, event_type="SLOT_RELEASED", actor_id=user_id, reason=reason or "Slot manually released"))
        db.commit(); db.refresh(slot)
        logger.info("slot_release_completed slot_code=%s", slot_code)
        return slot
    except HTTPException:
        db.rollback(); raise
    except SQLAlchemyError as exc:
        db.rollback(); logger.error("slot_release_failed slot_code=%s", slot_code, exc_info=True); raise RuntimeError(f"Database error while releasing slot: {exc}") from exc


def expire_holds(db: Session) -> int:
    logger.info("expire_holds_started")
    try:
        now = utc_now()
        expired_holds = db.query(SlotHold).filter(SlotHold.status == ReservationStatus.HELD, SlotHold.expires_at <= now).with_for_update().all()
        expired_count = 0
        for hold in expired_holds:
            slot = db.query(ParkingSlot).filter(ParkingSlot.slot_id == hold.slot_id).with_for_update().first()
            if not slot:
                continue
            old_status = slot.status
            hold.status = ReservationStatus.EXPIRED; hold.updated_at = now
            slot.status = SlotStatus.AVAILABLE; slot.updated_at = now
            db.add(SlotEvent(slot_id=slot.slot_id, old_status=old_status, new_status=SlotStatus.AVAILABLE, event_type="HOLD_EXPIRED", actor_id="system", reason="Hold expired automatically"))
            expired_count += 1
        db.commit(); logger.info("expire_holds_completed expired_count=%s", expired_count)
        return expired_count
    except SQLAlchemyError as exc:
        db.rollback(); logger.error("expire_holds_failed", exc_info=True); raise RuntimeError(f"Database error while expiring holds: {exc}") from exc
