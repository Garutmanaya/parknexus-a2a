"""FastAPI router for ParkNexus A2A Host Agent."""

from fastapi import APIRouter, HTTPException

from platform_services.host_agent import service, system_health, transaction_service, user_service
from platform_services.host_agent.graph import run_host_agent
from platform_services.host_agent.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AgentsResponse,
    CancelHoldRequest,
    ChatParkingRequest,
    ConfirmParkingRequest,
    CreateUserRequest,
    FindParkingRequest,
    FindParkingResponse,
    GarageLayoutByProviderRequest,
    HoldParkingRequest,
    ProvidersResponse,
    ProviderSummary,
    ReleaseSlotRequest,
    TransactionsResponse,
    UpdateUserRequest,
    UserLoginRequest,
    UserLoginResponse,
    UserResponse,
    UsersResponse,
    UserStatusRequest,
)
from shared.logging.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "healthy", "service": "host_agent"}


@router.get("/system/status")
def system_status():
    """Return environment health for admin dashboard."""
    logger.info("system_status_request_received")
    try:
        return system_health.get_system_status()
    except Exception as exc:
        logger.error("system_status_request_failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/user/login", response_model=UserLoginResponse)
def user_login(request: UserLoginRequest):
    logger.info("user_login_request_received user_id=%s", request.user_id)
    try:
        user = user_service.validate_user_login(request.user_id, request.password)
        return UserLoginResponse(authenticated=True, user=user, message="OK")
    except Exception as exc:
        logger.info("user_login_request_failed user_id=%s", request.user_id)
        return UserLoginResponse(authenticated=False, user=None, message=str(exc))


@router.post("/admin/login", response_model=AdminLoginResponse)
def admin_login(request: AdminLoginRequest):
    logger.info("admin_login_request_received username=%s", request.username)
    ok = user_service.validate_admin_login(request.username, request.password)
    return AdminLoginResponse(authenticated=ok, message="OK" if ok else "Invalid credentials")


@router.get("/admin/users", response_model=UsersResponse)
def admin_list_users():
    logger.info("admin_list_users_request_received")
    users = [UserResponse(**user) for user in user_service.list_users()]
    return UsersResponse(count=len(users), users=users)


@router.post("/admin/users", response_model=UserResponse)
def admin_create_user(request: CreateUserRequest):
    logger.info("admin_create_user_request_received user_id=%s email=%s", request.user_id, request.email)
    try:
        return UserResponse(**user_service.create_user(**request.model_dump()))
    except Exception as exc:
        logger.error("admin_create_user_request_failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/admin/users", response_model=UserResponse)
def admin_update_user(request: UpdateUserRequest):
    logger.info("admin_update_user_request_received user_id=%s", request.user_id)
    try:
        return UserResponse(**user_service.update_user(**request.model_dump(exclude_unset=True)))
    except Exception as exc:
        logger.error("admin_update_user_request_failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: str):
    logger.info("admin_delete_user_request_received user_id=%s", user_id)
    try:
        return user_service.delete_user(user_id)
    except Exception as exc:
        logger.error("admin_delete_user_request_failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/admin/users/status", response_model=UserResponse)
def admin_set_user_status(request: UserStatusRequest):
    logger.info("admin_set_user_status_request_received user_id=%s is_active=%s", request.user_id, request.is_active)
    try:
        return UserResponse(**user_service.set_user_active(request.user_id, request.is_active))
    except Exception as exc:
        logger.error("admin_set_user_status_request_failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/transactions", response_model=TransactionsResponse)
def list_transactions(user_id: str | None = None, limit: int = 25):
    logger.info("transactions_request_received user_id=%s limit=%s", user_id, limit)
    transactions = transaction_service.list_transactions(user_id=user_id, limit=limit)
    return TransactionsResponse(count=len(transactions), transactions=transactions)


@router.get("/providers", response_model=ProvidersResponse)
def list_providers():
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


@router.get("/admin/agents", response_model=AgentsResponse)
def admin_list_agents():
    logger.info("admin_list_agents_request_received")
    try:
        agents = service.list_providers()
        return AgentsResponse(count=len(agents), agents=agents)
    except Exception as exc:
        logger.error("admin_list_agents_request_failed", exc_info=True)
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
    logger.info("garage_layout_request_received provider_agent=%s", request.provider_agent)
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
