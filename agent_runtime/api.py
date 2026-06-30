"""
FastAPI router factory for ParkNexus A2A provider runtime.

This module creates provider-specific routers from:
- agent config
- provider DB session factory

The same router logic works for every provider agent.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from agent_runtime import service
from agent_runtime.models import ParkingSlot
from agent_runtime.schemas import (
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

from agent_runtime.a2a_card import build_agent_card
from fastapi import HTTPException
from agent_runtime.schemas import A2ARequest, A2AResponse
import asyncio
import json

from sse_starlette.sse import EventSourceResponse
from fastapi import APIRouter, Depends, Request
from shared.security.middleware import require_secure_a2a_request 
from decimal import Decimal

from shared.logging.logger import get_logger

logger = get_logger(__name__)

def parse_optional_decimal(value):
    """
    Convert optional JSON value to Decimal.

    A2A JSON may send numeric values as strings.
    """
    if value is None:
        return None

    return Decimal(str(value))


def create_db_dependency(session_factory: sessionmaker):
    """
    Create FastAPI dependency for the current provider DB.
    """

    def get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    return get_db


def create_provider_router(
    agent_config: dict,
    a2a_config: dict,
    session_factory: sessionmaker,
) -> APIRouter:
#def create_provider_router(agent_config: dict, session_factory: sessionmaker) -> APIRouter:
    """
    Create provider-specific API router.

    Args:
        agent_config: Resolved provider config.
        session_factory: SQLAlchemy session factory for provider DB.

    Returns:
        FastAPI APIRouter.
    """
    router = APIRouter()
    get_db = create_db_dependency(session_factory) 

    agent_card = build_agent_card(agent_config, a2a_config)

    @router.get("/.well-known/agent.json")
    def get_agent_json() -> dict:
        """
        Return A2A Agent Card.

        Kept for compatibility with examples that use /.well-known/agent.json.
        """
        return agent_card

    @router.get("/.well-known/agent-card.json")
    def get_agent_card_json() -> dict:
        """
        Return A2A Agent Card.

        Current A2A references also use /.well-known/agent-card.json.
        """
        return agent_card

    @router.get("/health")
    def health(db: Session = Depends(get_db)) -> dict:
        """
        Health check for provider agent.
        """
        db.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "service": "provider_agent",
            "agent_id": agent_config["agent_id"],
            "display_name": agent_config["display_name"],
        }

    @router.post("/slots/search", response_model=SlotSearchResponse)
    def search_slots(
        request: SlotSearchRequest,
        db: Session = Depends(get_db),
    ):
        """
        Search available slots in current provider DB.
        """
        slots = service.search_available_slots(
            db=db,
            level_name=request.level_name,
            slot_type=request.slot_type,
            ev_charger=request.ev_charger,
            handicap=request.handicap,
            max_price_per_hour=request.max_price_per_hour,
            limit=request.limit,
        )

        return SlotSearchResponse(count=len(slots), slots=slots)

    @router.get("/slots/{slot_code}")
    def get_slot(
        slot_code: str,
        db: Session = Depends(get_db),
    ):
        """
        Get one slot by slot code.
        """
        slot = service.get_slot_by_code(db, slot_code)

        if not slot:
            return {"status": "not_found", "slot_code": slot_code}

        return slot

    @router.post("/slots/hold", response_model=HoldSlotResponse)
    def hold_slot(
        request: HoldSlotRequest,
        db: Session = Depends(get_db),
    ):
        """
        Hold an available slot.
        """
        hold = service.hold_slot(
            db=db,
            slot_code=request.slot_code,
            user_id=request.user_id,
            hold_minutes=request.hold_minutes,
        )

        slot = (
            db.query(ParkingSlot)
            .filter(ParkingSlot.slot_id == hold.slot_id)
            .first()
        )

        return HoldSlotResponse(
            hold_id=hold.hold_id,
            slot_id=hold.slot_id,
            slot_code=slot.slot_code,
            user_id=hold.user_id,
            status=hold.status.value,
            expires_at=hold.expires_at,
        )

    @router.post("/reservations/confirm", response_model=ReservationResponse)
    def confirm_reservation(
        request: ConfirmReservationRequest,
        db: Session = Depends(get_db),
    ):
        """
        Confirm a held slot.
        """
        reservation = service.confirm_reservation(
            db=db,
            hold_id=request.hold_id,
            user_id=request.user_id,
            reserved_minutes=request.reserved_minutes,
        )

        slot = (
            db.query(ParkingSlot)
            .filter(ParkingSlot.slot_id == reservation.slot_id)
            .first()
        )

        return ReservationResponse(
            reservation_id=reservation.reservation_id,
            hold_id=reservation.hold_id,
            slot_id=reservation.slot_id,
            slot_code=slot.slot_code,
            user_id=reservation.user_id,
            status=reservation.status.value,
            reserved_from=reservation.reserved_from,
            reserved_until=reservation.reserved_until,
            total_price=reservation.total_price,
        )

    @router.post("/holds/cancel", response_model=WorkflowResponse)
    def cancel_hold(
        request: CancelHoldRequest,
        db: Session = Depends(get_db),
    ):
        """
        Cancel active hold.
        """
        slot = service.cancel_hold(
            db=db,
            hold_id=request.hold_id,
            user_id=request.user_id,
        )

        return WorkflowResponse(
            status="success",
            message="Hold cancelled successfully",
            slot_code=slot.slot_code,
        )

    @router.post("/slots/release", response_model=WorkflowResponse)
    def release_slot(
        request: ReleaseSlotRequest,
        db: Session = Depends(get_db),
    ):
        """
        Release slot back to available.
        """
        slot = service.release_slot(
            db=db,
            slot_code=request.slot_code,
            user_id=request.user_id,
            reason=request.reason,
        )

        return WorkflowResponse(
            status="success",
            message="Slot released successfully",
            slot_code=slot.slot_code,
        )

    @router.post("/holds/expire", response_model=WorkflowResponse)
    def expire_holds(db: Session = Depends(get_db)):
        """
        Manually expire stale holds.
        """
        expired_count = service.expire_holds(db)

        return WorkflowResponse(
            status="success",
            message=f"Expired holds processed: {expired_count}",
        )

    async def build_sse_event(event_name: str, payload: dict) -> dict:
        """
        Build SSE event payload.

        SSE format:
            event: <event_name>
            data: <json payload>
        """
        return {
            "event": event_name,
            "data": json.dumps(payload),
        }

    def parse_optional_int(value):
        if value is None:
            return None

        return int(value)
    

    @router.post("/a2a", response_model=A2AResponse)
    async def handle_a2a_request(
        request: A2ARequest,
        security_context: dict = Depends(require_secure_a2a_request),
        db: Session = Depends(get_db),
    ):
    #@router.post("/a2a", response_model=A2AResponse)
    #def handle_a2a_request(
    #    request: A2ARequest,
    #    db: Session = Depends(get_db),
    #):
        """
        Minimal A2A-compatible JSON-RPC endpoint.

        Supported methods:
            - search_slots
            - hold_slot
            - confirm_reservation
            - release_slot
            - cancel_hold
            - expire_holds
        """
        try:
            if request.method == "search_slots":
                
                slots = service.search_available_slots(
                    db=db,
                    level_name=request.params.get("level_name"),
                    slot_type=request.params.get("slot_type"),
                    ev_charger=request.params.get("ev_charger"),
                    handicap=request.params.get("handicap"),
                    #max_price_per_hour=request.params.get("max_price_per_hour"),
                    max_price_per_hour=parse_optional_decimal(request.params.get("max_price_per_hour")),
                    limit=request.params.get("limit", 50),
                    budget_amount=parse_optional_decimal(request.params.get("budget_amount")),
                    budget_unit=request.params.get("budget_unit"),
                    duration_minutes=parse_optional_int(request.params.get("duration_minutes")),
                    
                )

                return A2AResponse(
                    id=request.id,
                    result={
                        "agent_id": agent_config["agent_id"],
                        "count": len(slots),
                        "slots": [
                            {
                                "slot_id": slot.slot_id,
                                "slot_code": slot.slot_code,
                                "level_name": slot.level_name,
                                "row_label": slot.row_label,
                                "column_number": slot.column_number,
                                "slot_type": slot.slot_type.value,
                                "status": slot.status.value,
                                "price_per_hour": str(slot.price_per_hour),
                                "hourly_rate": str(slot.price_per_hour),
                                "daily_rate": str(slot.daily_rate) if slot.daily_rate is not None else None,
                                "monthly_rate": str(slot.monthly_rate) if slot.monthly_rate is not None else None,
                                "estimated_price": str(
                                    service.calculate_estimated_price(
                                        slot,
                                        request.params.get("budget_unit"),
                                        parse_optional_int(request.params.get("duration_minutes")),
                                    )
                                ),
                                "estimated_price_unit": request.params.get("budget_unit") or "hour",
                                "distance_to_entrance_meters": slot.distance_to_entrance_meters,
                                "ev_charger": slot.ev_charger,
                                "handicap": slot.handicap,
                            }
                            for slot in slots
                        ],
                    },
                )

            if request.method == "hold_slot":
                hold = service.hold_slot(
                    db=db,
                    slot_code=request.params["slot_code"],
                    user_id=request.params["user_id"],
                    hold_minutes=request.params.get("hold_minutes", 5),
                )

                slot = (
                    db.query(ParkingSlot)
                    .filter(ParkingSlot.slot_id == hold.slot_id)
                    .first()
                )

                return A2AResponse(
                    id=request.id,
                    result={
                        "agent_id": agent_config["agent_id"],
                        "hold_id": hold.hold_id,
                        "slot_id": hold.slot_id,
                        "slot_code": slot.slot_code,
                        "user_id": hold.user_id,
                        "status": hold.status.value,
                        "expires_at": hold.expires_at.isoformat(),
                    },
                )

            if request.method == "confirm_reservation":
                reservation = service.confirm_reservation(
                    db=db,
                    hold_id=request.params["hold_id"],
                    user_id=request.params["user_id"],
                    reserved_minutes=request.params.get("reserved_minutes", 60),
                )

                slot = (
                    db.query(ParkingSlot)
                    .filter(ParkingSlot.slot_id == reservation.slot_id)
                    .first()
                )

                return A2AResponse(
                    id=request.id,
                    result={
                        "agent_id": agent_config["agent_id"],
                        "reservation_id": reservation.reservation_id,
                        "hold_id": reservation.hold_id,
                        "slot_id": reservation.slot_id,
                        "slot_code": slot.slot_code,
                        "user_id": reservation.user_id,
                        "status": reservation.status.value,
                        "reserved_from": reservation.reserved_from.isoformat(),
                        "reserved_until": reservation.reserved_until.isoformat(),
                        "total_price": str(reservation.total_price),
                    },
                )

            if request.method == "release_slot":
                slot = service.release_slot(
                    db=db,
                    slot_code=request.params["slot_code"],
                    user_id=request.params["user_id"],
                    reason=request.params.get("reason"),
                )

                return A2AResponse(
                    id=request.id,
                    result={
                        "agent_id": agent_config["agent_id"],
                        "status": "success",
                        "message": "Slot released successfully",
                        "slot_code": slot.slot_code,
                    },
                )

            if request.method == "cancel_hold":
                slot = service.cancel_hold(
                    db=db,
                    hold_id=request.params["hold_id"],
                    user_id=request.params["user_id"],
                )

                return A2AResponse(
                    id=request.id,
                    result={
                        "agent_id": agent_config["agent_id"],
                        "status": "success",
                        "message": "Hold cancelled successfully",
                        "slot_code": slot.slot_code,
                    },
                )

            if request.method == "expire_holds":
                expired_count = service.expire_holds(db)

                return A2AResponse(
                    id=request.id,
                    result={
                        "agent_id": agent_config["agent_id"],
                        "status": "success",
                        "expired_count": expired_count,
                    },
                )

            return A2AResponse(
                id=request.id,
                error={
                    "code": -32601,
                    "message": f"Unsupported A2A method: {request.method}",
                },
            )

        except HTTPException as exc:
            return A2AResponse(
                id=request.id,
                error={
                    "code": exc.status_code,
                    "message": exc.detail,
                },
            )

        except KeyError as exc:
            return A2AResponse(
                id=request.id,
                error={
                    "code": -32602,
                    "message": f"Missing required parameter: {exc}",
                },
            )

        except Exception as exc:
            return A2AResponse(
                id=request.id,
                error={
                    "code": -32603,
                    "message": str(exc),
                },
            )
        
    @router.post("/a2a/stream")
    async def handle_a2a_stream_request(
        request: A2ARequest,
        security_context: dict = Depends(require_secure_a2a_request),
        db: Session = Depends(get_db),
    ):
    #@router.post("/a2a/stream")
    #async def handle_a2a_stream_request(
    #    request: A2ARequest,
    #    db: Session = Depends(get_db),
    #):
        """
        A2A SSE streaming endpoint.

        This endpoint streams progress events and then a final result.

        Supported methods:
            - search_slots
            - hold_slot
            - confirm_reservation
            - release_slot
            - cancel_hold
            - expire_holds
        """

        async def event_generator():
            """
            Generate SSE events for A2A task execution.
            """
            yield await build_sse_event(
                "task_started",
                {
                    "request_id": request.id,
                    "agent_id": agent_config["agent_id"],
                    "method": request.method,
                    "status": "started",
                },
            )

            await asyncio.sleep(0.05)

            try:
                yield await build_sse_event(
                    "task_progress",
                    {
                        "request_id": request.id,
                        "agent_id": agent_config["agent_id"],
                        "method": request.method,
                        "status": "processing",
                    },
                )

                if request.method == "search_slots":
                    slots = service.search_available_slots(
                        db=db,
                        level_name=request.params.get("level_name"),
                        slot_type=request.params.get("slot_type"),
                        ev_charger=request.params.get("ev_charger"),
                        handicap=request.params.get("handicap"),
                        #max_price_per_hour=request.params.get("max_price_per_hour"),
                        budget_amount=parse_optional_decimal(request.params.get("budget_amount")),
                        budget_unit=request.params.get("budget_unit"),
                        duration_minutes=parse_optional_int(request.params.get("duration_minutes")),
                        max_price_per_hour=parse_optional_decimal(request.params.get("max_price_per_hour")),
                        limit=request.params.get("limit", 50),
                    )

                    yield await build_sse_event(
                        "task_progress",
                        {
                            "request_id": request.id,
                            "agent_id": agent_config["agent_id"],
                            "status": "slots_found",
                            "count": len(slots),
                        },
                    )

                    result = {
                        "jsonrpc": "2.0",
                        "id": request.id,
                        "result": {
                            "agent_id": agent_config["agent_id"],
                            "count": len(slots),
                            "slots": [
                                {
                                    "slot_id": slot.slot_id,
                                    "slot_code": slot.slot_code,
                                    "level_name": slot.level_name,
                                    "row_label": slot.row_label,
                                    "column_number": slot.column_number,
                                    "slot_type": slot.slot_type.value,
                                    "status": slot.status.value,
                                    "price_per_hour": str(slot.price_per_hour),
                                    "hourly_rate": str(slot.price_per_hour),
                                    "daily_rate": str(slot.daily_rate) if slot.daily_rate is not None else None,
                                    "monthly_rate": str(slot.monthly_rate) if slot.monthly_rate is not None else None,
                                    "estimated_price": str(
                                        service.calculate_estimated_price(
                                            slot,
                                            request.params.get("budget_unit"),
                                            parse_optional_int(request.params.get("duration_minutes")),
                                        )
                                    ),
                                    "estimated_price_unit": request.params.get("budget_unit") or "hour",
                                    "distance_to_entrance_meters": slot.distance_to_entrance_meters,
                                    "ev_charger": slot.ev_charger,
                                    "handicap": slot.handicap,
                                }
                                for slot in slots
                            ],
                        },
                        "error": None,
                    }

                    yield await build_sse_event("task_completed", result)
                    return

                if request.method == "hold_slot":
                    hold = service.hold_slot(
                        db=db,
                        slot_code=request.params["slot_code"],
                        user_id=request.params["user_id"],
                        hold_minutes=request.params.get("hold_minutes", 5),
                    )

                    slot = (
                        db.query(ParkingSlot)
                        .filter(ParkingSlot.slot_id == hold.slot_id)
                        .first()
                    )

                    result = {
                        "jsonrpc": "2.0",
                        "id": request.id,
                        "result": {
                            "agent_id": agent_config["agent_id"],
                            "hold_id": hold.hold_id,
                            "slot_id": hold.slot_id,
                            "slot_code": slot.slot_code,
                            "user_id": hold.user_id,
                            "status": hold.status.value,
                            "expires_at": hold.expires_at.isoformat(),
                        },
                        "error": None,
                    }

                    yield await build_sse_event("task_completed", result)
                    return

                if request.method == "confirm_reservation":
                    reservation = service.confirm_reservation(
                        db=db,
                        hold_id=request.params["hold_id"],
                        user_id=request.params["user_id"],
                        reserved_minutes=request.params.get("reserved_minutes", 60),
                    )

                    slot = (
                        db.query(ParkingSlot)
                        .filter(ParkingSlot.slot_id == reservation.slot_id)
                        .first()
                    )

                    result = {
                        "jsonrpc": "2.0",
                        "id": request.id,
                        "result": {
                            "agent_id": agent_config["agent_id"],
                            "reservation_id": reservation.reservation_id,
                            "hold_id": reservation.hold_id,
                            "slot_id": reservation.slot_id,
                            "slot_code": slot.slot_code,
                            "user_id": reservation.user_id,
                            "status": reservation.status.value,
                            "reserved_from": reservation.reserved_from.isoformat(),
                            "reserved_until": reservation.reserved_until.isoformat(),
                            "total_price": str(reservation.total_price),
                        },
                        "error": None,
                    }

                    yield await build_sse_event("task_completed", result)
                    return

                if request.method == "release_slot":
                    slot = service.release_slot(
                        db=db,
                        slot_code=request.params["slot_code"],
                        user_id=request.params["user_id"],
                        reason=request.params.get("reason"),
                    )

                    result = {
                        "jsonrpc": "2.0",
                        "id": request.id,
                        "result": {
                            "agent_id": agent_config["agent_id"],
                            "status": "success",
                            "message": "Slot released successfully",
                            "slot_code": slot.slot_code,
                        },
                        "error": None,
                    }

                    yield await build_sse_event("task_completed", result)
                    return

                if request.method == "cancel_hold":
                    slot = service.cancel_hold(
                        db=db,
                        hold_id=request.params["hold_id"],
                        user_id=request.params["user_id"],
                    )

                    result = {
                        "jsonrpc": "2.0",
                        "id": request.id,
                        "result": {
                            "agent_id": agent_config["agent_id"],
                            "status": "success",
                            "message": "Hold cancelled successfully",
                            "slot_code": slot.slot_code,
                        },
                        "error": None,
                    }

                    yield await build_sse_event("task_completed", result)
                    return

                if request.method == "expire_holds":
                    expired_count = service.expire_holds(db)

                    result = {
                        "jsonrpc": "2.0",
                        "id": request.id,
                        "result": {
                            "agent_id": agent_config["agent_id"],
                            "status": "success",
                            "expired_count": expired_count,
                        },
                        "error": None,
                    }

                    yield await build_sse_event("task_completed", result)
                    return

                yield await build_sse_event(
                    "task_failed",
                    {
                        "jsonrpc": "2.0",
                        "id": request.id,
                        "result": None,
                        "error": {
                            "code": -32601,
                            "message": f"Unsupported A2A method: {request.method}",
                        },
                    },
                )

            except HTTPException as exc:
                yield await build_sse_event(
                    "task_failed",
                    {
                        "jsonrpc": "2.0",
                        "id": request.id,
                        "result": None,
                        "error": {
                            "code": exc.status_code,
                            "message": exc.detail,
                        },
                    },
                )

            except KeyError as exc:
                yield await build_sse_event(
                    "task_failed",
                    {
                        "jsonrpc": "2.0",
                        "id": request.id,
                        "result": None,
                        "error": {
                            "code": -32602,
                            "message": f"Missing required parameter: {exc}",
                        },
                    },
                )

            except Exception as exc:
                yield await build_sse_event(
                    "task_failed",
                    {
                        "jsonrpc": "2.0",
                        "id": request.id,
                        "result": None,
                        "error": {
                            "code": -32603,
                            "message": str(exc),
                        },
                    },
                )

        return EventSourceResponse(event_generator())
    return router


if __name__ == "__main__":
    """
    Manual test:
        python -m agent_runtime.api
    """
    print("Provider API router factory loaded successfully")
