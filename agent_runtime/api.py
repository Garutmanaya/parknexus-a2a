"""FastAPI router factory for ParkNexus A2A provider runtime."""

import asyncio
import json
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from sse_starlette.sse import EventSourceResponse

from agent_runtime import service
from agent_runtime.a2a_card import build_agent_card
from agent_runtime.models import ParkingSlot
from agent_runtime.schemas import (
    A2ARequest,
    A2AResponse,
    CancelHoldRequest,
    ConfirmReservationRequest,
    HoldSlotRequest,
    HoldSlotResponse,
    ReleaseSlotRequest,
    ReservationResponse,
    SlotSearchRequest,
    SlotSearchResponse,
    WorkflowResponse,
)
from shared.logging.logger import get_logger
from shared.security.middleware import require_secure_a2a_request

logger = get_logger(__name__)


def parse_optional_decimal(value):
    return None if value is None else Decimal(str(value))


def parse_optional_int(value):
    return None if value is None else int(value)


def slot_to_dict(slot: ParkingSlot, budget_unit: str | None = None, duration_minutes: int | None = None) -> dict:
    return {
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
        "estimated_price": str(service.calculate_estimated_price(slot, budget_unit, duration_minutes)),
        "estimated_price_unit": budget_unit or ("total" if duration_minutes else "hour"),
        "distance_to_entrance_meters": slot.distance_to_entrance_meters,
        "ev_charger": slot.ev_charger,
        "handicap": slot.handicap,
    }


def create_db_dependency(session_factory: sessionmaker):
    def get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()
    return get_db


def create_provider_router(agent_config: dict, a2a_config: dict, session_factory: sessionmaker) -> APIRouter:
    router = APIRouter()
    get_db = create_db_dependency(session_factory)
    agent_card = build_agent_card(agent_config, a2a_config)

    @router.get("/.well-known/agent.json")
    def get_agent_json() -> dict:
        return agent_card

    @router.get("/.well-known/agent-card.json")
    def get_agent_card_json() -> dict:
        return agent_card

    @router.get("/health")
    def health(db: Session = Depends(get_db)) -> dict:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "service": "provider_agent", "agent_id": agent_config["agent_id"], "display_name": agent_config["display_name"]}

    @router.post("/slots/search", response_model=SlotSearchResponse)
    def search_slots(request: SlotSearchRequest, db: Session = Depends(get_db)):
        logger.info("rest_slot_search_received agent_id=%s", agent_config["agent_id"])
        logger.debug("rest_slot_search_payload=%s", request.model_dump())
        slots = service.search_available_slots(
            db=db,
            level_name=request.level_name,
            slot_type=request.slot_type,
            ev_charger=request.ev_charger,
            handicap=request.handicap,
            max_hourly_rate=request.max_hourly_rate,
            budget_amount=request.budget_amount,
            budget_unit=request.budget_unit,
            duration_minutes=request.duration_minutes,
            limit=request.limit,
        )
        return SlotSearchResponse(count=len(slots), slots=slots)

    @router.get("/slots/{slot_code}")
    def get_slot(slot_code: str, db: Session = Depends(get_db)):
        slot = service.get_slot_by_code(db, slot_code)
        if not slot:
            return {"status": "not_found", "slot_code": slot_code}
        return slot

    @router.get("/garage/layout")
    def get_garage_layout(db: Session = Depends(get_db)) -> dict:
        logger.info("garage_layout_requested agent_id=%s", agent_config["agent_id"])
        return service.get_garage_layout(db)

    @router.post("/slots/hold", response_model=HoldSlotResponse)
    def hold_slot(request: HoldSlotRequest, db: Session = Depends(get_db)):
        logger.info("rest_hold_received slot_code=%s user_id=%s", request.slot_code, request.user_id)
        hold = service.hold_slot(db, request.slot_code, request.user_id, request.hold_minutes)
        slot = db.query(ParkingSlot).filter(ParkingSlot.slot_id == hold.slot_id).first()
        return HoldSlotResponse(hold_id=hold.hold_id, slot_id=hold.slot_id, slot_code=slot.slot_code, user_id=hold.user_id, status=hold.status.value, expires_at=hold.expires_at)

    @router.post("/reservations/confirm", response_model=ReservationResponse)
    def confirm_reservation(request: ConfirmReservationRequest, db: Session = Depends(get_db)):
        logger.info("rest_confirm_received hold_id=%s user_id=%s", request.hold_id, request.user_id)
        reservation = service.confirm_reservation(db, request.hold_id, request.user_id, request.reserved_minutes)
        slot = db.query(ParkingSlot).filter(ParkingSlot.slot_id == reservation.slot_id).first()
        return ReservationResponse(reservation_id=reservation.reservation_id, hold_id=reservation.hold_id, slot_id=reservation.slot_id, slot_code=slot.slot_code, user_id=reservation.user_id, status=reservation.status.value, reserved_from=reservation.reserved_from, reserved_until=reservation.reserved_until, total_price=reservation.total_price)

    @router.post("/holds/cancel", response_model=WorkflowResponse)
    def cancel_hold(request: CancelHoldRequest, db: Session = Depends(get_db)):
        logger.info("rest_cancel_hold_received hold_id=%s user_id=%s", request.hold_id, request.user_id)
        slot = service.cancel_hold(db, request.hold_id, request.user_id)
        return WorkflowResponse(status="success", message="Hold cancelled successfully", slot_code=slot.slot_code)

    @router.post("/slots/release", response_model=WorkflowResponse)
    def release_slot(request: ReleaseSlotRequest, db: Session = Depends(get_db)):
        logger.info("rest_release_slot_received slot_code=%s user_id=%s", request.slot_code, request.user_id)
        slot = service.release_slot(db, request.slot_code, request.user_id, request.reason)
        return WorkflowResponse(status="success", message="Slot released successfully", slot_code=slot.slot_code)

    def execute_a2a(request: A2ARequest, db: Session) -> A2AResponse:
        logger.info("a2a_request_received agent_id=%s method=%s request_id=%s", agent_config["agent_id"], request.method, request.id)
        logger.debug("a2a_request_params=%s", request.params)
        try:
            if request.method == "get_garage_layout":
                return A2AResponse(id=request.id, result={"agent_id": agent_config["agent_id"], **service.get_garage_layout(db)})
            if request.method == "search_slots":
                duration = parse_optional_int(request.params.get("duration_minutes"))
                slots = service.search_available_slots(
                    db=db,
                    level_name=request.params.get("level_name"),
                    slot_type=request.params.get("slot_type"),
                    ev_charger=request.params.get("ev_charger"),
                    handicap=request.params.get("handicap"),
                    max_hourly_rate=parse_optional_decimal(request.params.get("max_hourly_rate")),
                    budget_amount=parse_optional_decimal(request.params.get("budget_amount")),
                    budget_unit=request.params.get("budget_unit"),
                    duration_minutes=duration,
                    limit=request.params.get("limit", 50),
                )
                return A2AResponse(id=request.id, result={"agent_id": agent_config["agent_id"], "count": len(slots), "slots": [slot_to_dict(slot, request.params.get("budget_unit"), duration) for slot in slots]})
            if request.method == "hold_slot":
                hold = service.hold_slot(db, request.params["slot_code"], request.params["user_id"], request.params.get("hold_minutes", 5))
                slot = db.query(ParkingSlot).filter(ParkingSlot.slot_id == hold.slot_id).first()
                return A2AResponse(id=request.id, result={"agent_id": agent_config["agent_id"], "hold_id": hold.hold_id, "slot_id": hold.slot_id, "slot_code": slot.slot_code, "user_id": hold.user_id, "status": hold.status.value, "expires_at": hold.expires_at.isoformat()})
            if request.method == "confirm_reservation":
                reservation = service.confirm_reservation(db, request.params["hold_id"], request.params["user_id"], request.params.get("reserved_minutes", 60))
                slot = db.query(ParkingSlot).filter(ParkingSlot.slot_id == reservation.slot_id).first()
                return A2AResponse(id=request.id, result={"agent_id": agent_config["agent_id"], "reservation_id": reservation.reservation_id, "hold_id": reservation.hold_id, "slot_id": reservation.slot_id, "slot_code": slot.slot_code, "user_id": reservation.user_id, "status": reservation.status.value, "reserved_from": reservation.reserved_from.isoformat(), "reserved_until": reservation.reserved_until.isoformat(), "total_price": str(reservation.total_price)})
            if request.method == "release_slot":
                slot = service.release_slot(db, request.params["slot_code"], request.params["user_id"], request.params.get("reason"))
                return A2AResponse(id=request.id, result={"agent_id": agent_config["agent_id"], "status": "success", "message": "Slot released successfully", "slot_code": slot.slot_code})
            if request.method == "cancel_hold":
                slot = service.cancel_hold(db, request.params["hold_id"], request.params["user_id"])
                return A2AResponse(id=request.id, result={"agent_id": agent_config["agent_id"], "status": "success", "message": "Hold cancelled successfully", "slot_code": slot.slot_code})
            if request.method == "expire_holds":
                expired_count = service.expire_holds(db)
                return A2AResponse(id=request.id, result={"agent_id": agent_config["agent_id"], "status": "success", "expired_count": expired_count})
            return A2AResponse(id=request.id, error={"code": -32601, "message": f"Unsupported A2A method: {request.method}"})
        except HTTPException as exc:
            return A2AResponse(id=request.id, error={"code": exc.status_code, "message": exc.detail})
        except KeyError as exc:
            return A2AResponse(id=request.id, error={"code": -32602, "message": f"Missing required parameter: {exc}"})
        except Exception as exc:
            logger.error("a2a_request_failed method=%s", request.method, exc_info=True)
            return A2AResponse(id=request.id, error={"code": -32603, "message": str(exc)})

    @router.post("/a2a", response_model=A2AResponse)
    async def handle_a2a_request(request: A2ARequest, security_context: dict = Depends(require_secure_a2a_request), db: Session = Depends(get_db)):
        return execute_a2a(request, db)

    @router.post("/a2a/stream")
    async def handle_a2a_stream_request(request: A2ARequest, security_context: dict = Depends(require_secure_a2a_request), db: Session = Depends(get_db)):
        async def event_generator():
            yield {"event": "task_started", "data": json.dumps({"request_id": request.id, "agent_id": agent_config["agent_id"], "method": request.method, "status": "started"})}
            await asyncio.sleep(0.05)
            result = execute_a2a(request, db).model_dump()
            event_name = "task_failed" if result.get("error") else "task_completed"
            yield {"event": event_name, "data": json.dumps(result, default=str)}
        return EventSourceResponse(event_generator())

    return router
