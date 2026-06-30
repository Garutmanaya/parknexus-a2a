"""
FastAPI router for ParkNexus A2A Host Agent.
"""

from fastapi import APIRouter, HTTPException

from platform_services.host_agent.schemas import FindParkingRequest, FindParkingResponse
from platform_services.host_agent import service
from platform_services.host_agent.intent import parse_user_request
from platform_services.host_agent.schemas import ChatParkingRequest, ChatParkingResponse

from platform_services.host_agent.intent import parse_user_request
from platform_services.host_agent.graph import run_host_agent
from platform_services.host_agent.schemas import (
    HoldParkingRequest,
    ConfirmParkingRequest,
    CancelHoldRequest,
    ReleaseSlotRequest,
)

from shared.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health")
def health() -> dict:
    """
    Host Agent health check.
    """
    return {
        "status": "healthy",
        "service": "host_agent",
    }


@router.post("/parking/find", response_model=FindParkingResponse)
def find_parking(request: FindParkingRequest):
    """
    Find parking across registered provider agents.
    """
    try:
        slots = service.find_parking(
            level_name=request.level_name,
            ev_charger=request.ev_charger,
            handicap=request.handicap,
            max_price_per_hour=request.max_price_per_hour,
            limit_per_provider=request.limit_per_provider,
        )

        return FindParkingResponse(
            count=len(slots),
            slots=slots,
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/parking/chat")
def chat_parking(request: ChatParkingRequest):
    """
    Natural language Host Agent endpoint powered by LangGraph.
    """
    try:
        return run_host_agent(request.message)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/parking/chat", response_model=ChatParkingResponse)
def chat_parking_intent(request: ChatParkingRequest):
    """
    Natural language parking search endpoint.
    """
    try:
        intent = parse_user_request(request.message)

        if intent.intent == "clarify":
            return ChatParkingResponse(
                intent=intent.model_dump(),
                count=0,
                slots=[],
            )

        max_price_per_hour = None
        if intent.budget_amount is not None and intent.budget_unit == "hour":
            max_price_per_hour = intent.budget_amount

        slots = service.find_parking(
            level_name=intent.level_name,
            ev_charger=intent.ev_charger,
            handicap=intent.handicap,
            max_price_per_hour=max_price_per_hour,
            limit_per_provider=5,
        )

        return ChatParkingResponse(
            intent=intent.model_dump(),
            count=len(slots),
            slots=slots,
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    
@router.post("/parking/hold")
def hold_parking(request: HoldParkingRequest):
    try:
        return service.hold_parking_slot(
            provider_url=request.provider_url,
            slot_code=request.slot_code,
            user_id=request.user_id,
            hold_minutes=request.hold_minutes,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/parking/confirm")
def confirm_parking(request: ConfirmParkingRequest):
    try:
        return service.confirm_parking_reservation(
            provider_url=request.provider_url,
            hold_id=request.hold_id,
            user_id=request.user_id,
            reserved_minutes=request.reserved_minutes,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/parking/hold/cancel")
def cancel_hold(request: CancelHoldRequest):
    try:
        return service.cancel_parking_hold(
            provider_url=request.provider_url,
            hold_id=request.hold_id,
            user_id=request.user_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/parking/release")
def release_slot(request: ReleaseSlotRequest):
    try:
        return service.release_parking_slot(
            provider_url=request.provider_url,
            slot_code=request.slot_code,
            user_id=request.user_id,
            reason=request.reason,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc