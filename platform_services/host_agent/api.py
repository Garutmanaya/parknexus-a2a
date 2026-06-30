"""FastAPI router for ParkNexus A2A Host Agent."""

from fastapi import APIRouter, HTTPException

from platform_services.host_agent import service
from platform_services.host_agent.graph import run_host_agent
from platform_services.host_agent.schemas import (
    CancelHoldRequest,
    ChatParkingRequest,
    ConfirmParkingRequest,
    FindParkingRequest,
    FindParkingResponse,
    GarageLayoutRequest,
    HoldParkingRequest,
    ReleaseSlotRequest,
)
from shared.logging.logger import get_logger

from platform_services.host_agent.schemas import (
    CancelHoldRequest,
    ChatParkingRequest,
    ConfirmParkingRequest,
    FindParkingRequest,
    FindParkingResponse,
    GarageLayoutByProviderRequest,
    GarageLayoutRequest,
    HoldParkingRequest,
    ProvidersResponse,
    ProviderSummary,
    ReleaseSlotRequest,
)

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "healthy", "service": "host_agent"}

@router.get("/providers", response_model=ProvidersResponse)
def list_providers():
    """
    List providers through Host Agent.

    UI must call this endpoint instead of talking to Registry or Provider directly.
    """
    logger.info("providers_request_received")

    try:
        providers = service.list_providers()

        result = [
            ProviderSummary(
                name=provider["name"],
                url=provider["url"],
                description=provider.get("description"),
                provider=provider.get("provider", {}),
                capabilities=provider.get("capabilities", {}),
                skills=provider.get("skills", []),
            )
            for provider in providers
        ]

        logger.info("providers_request_completed count=%s", len(result))

        return ProvidersResponse(count=len(result), providers=result)

    except Exception as exc:
        logger.error("providers_request_failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/parking/find", response_model=FindParkingResponse)
def find_parking(request: FindParkingRequest):
    logger.info("parking_find_request_received")
    logger.debug("parking_find_request_payload=%s", request.model_dump())
    try:
        slots = service.find_parking(**request.model_dump())
        logger.info("parking_find_request_completed count=%s", len(slots))
        return FindParkingResponse(count=len(slots), slots=slots)
    except Exception as exc:
        logger.error("parking_find_request_failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/parking/chat")
def chat_parking(request: ChatParkingRequest):
    logger.info("parking_chat_request_received")
    logger.debug("parking_chat_request_payload=%s", request.model_dump())
    try:
        return run_host_agent(request.message)
    except Exception as exc:
        logger.error("parking_chat_request_failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/garage/layout")
def garage_layout(request: GarageLayoutByProviderRequest):
    """
    Return garage layout by provider agent name.

    Browser sends provider_agent only.
    Host resolves provider URL internally through Registry.
    """
    logger.info(
        "garage_layout_request_received provider_agent=%s",
        request.provider_agent,
    )
    logger.debug("garage_layout_request_payload=%s", request.model_dump())

    try:
        return service.get_garage_layout_by_provider_agent(request.provider_agent)

    except Exception as exc:
        logger.error("garage_layout_request_failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.post("/parking/hold")
def hold_parking(request: HoldParkingRequest):
    logger.info("parking_hold_request_received provider_url=%s slot_code=%s user_id=%s", request.provider_url, request.slot_code, request.user_id)
    logger.debug("parking_hold_request_payload=%s", request.model_dump())
    try:
        return service.hold_parking_slot(request.provider_url, request.slot_code, request.user_id, request.hold_minutes)
    except Exception as exc:
        logger.error("parking_hold_request_failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/parking/confirm")
def confirm_parking(request: ConfirmParkingRequest):
    logger.info("parking_confirm_request_received provider_url=%s hold_id=%s user_id=%s", request.provider_url, request.hold_id, request.user_id)
    logger.debug("parking_confirm_request_payload=%s", request.model_dump())
    try:
        return service.confirm_parking_reservation(request.provider_url, request.hold_id, request.user_id, request.reserved_minutes)
    except Exception as exc:
        logger.error("parking_confirm_request_failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/parking/hold/cancel")
def cancel_hold(request: CancelHoldRequest):
    logger.info("parking_cancel_hold_request_received provider_url=%s hold_id=%s user_id=%s", request.provider_url, request.hold_id, request.user_id)
    try:
        return service.cancel_parking_hold(request.provider_url, request.hold_id, request.user_id)
    except Exception as exc:
        logger.error("parking_cancel_hold_request_failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/parking/release")
def release_slot(request: ReleaseSlotRequest):
    logger.info("parking_release_request_received provider_url=%s slot_code=%s user_id=%s", request.provider_url, request.slot_code, request.user_id)
    try:
        return service.release_parking_slot(request.provider_url, request.slot_code, request.user_id, request.reason)
    except Exception as exc:
        logger.error("parking_release_request_failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
