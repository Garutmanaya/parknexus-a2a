"""Service layer for ParkNexus A2A Host Agent."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal

from shared.config.runtime import get_httpx_verify_tls, get_registry_agent_base_url
from platform_services.host_agent.schemas import ProviderSlotResult
from shared.security.a2a_client import post_a2a
from shared.logging.logger import get_logger

logger = get_logger(__name__)


def discover_search_agents() -> list[dict]:
    registry_url = get_registry_agent_base_url()
    payload = {"jsonrpc": "2.0", "id": "host-discover-search-agents", "method": "discover_agents", "params": {"skill_id": "search_slots", "streaming_required": True}}
    logger.info("registry_discovery_started")
    logger.debug("registry_discovery_payload=%s", payload)
    response = post_a2a(url=f"{registry_url}/a2a", payload=payload, verify_tls=get_httpx_verify_tls())
    if response.get("error"):
        raise RuntimeError(response["error"]["message"])
    agents = response["result"]["agents"]
    logger.info("registry_discovery_completed count=%s", len(agents))
    logger.debug("registry_discovery_agents=%s", agents)
    return agents

def list_providers() -> list[dict]:
    """
    List providers through secure Registry A2A.
    """
    registry_url = get_registry_agent_base_url()

    payload = {
        "jsonrpc": "2.0",
        "id": "host-list-providers",
        "method": "list_agents",
        "params": {},
    }

    logger.info("provider_list_started")
    logger.debug("provider_list_payload=%s", payload)

    response = post_a2a(
        url=f"{registry_url}/a2a",
        payload=payload,
        verify_tls=get_httpx_verify_tls(),
    )

    if response.get("error"):
        raise RuntimeError(response["error"]["message"])

    providers = response["result"]["agents"]

    logger.info("provider_list_completed count=%s", len(providers))
    logger.debug("provider_list_result=%s", providers)

    return providers


def get_provider_by_name(provider_agent: str) -> dict:
    """
    Resolve provider agent metadata by provider agent name.
    """
    providers = list_providers()

    for provider in providers:
        if provider["name"] == provider_agent:
            return provider

    raise RuntimeError(f"Provider not found: {provider_agent}")


def get_garage_layout_by_provider_agent(provider_agent: str) -> dict:
    """
    Get garage layout by provider agent name.

    UI should call this instead of passing provider_url directly.
    """
    provider = get_provider_by_name(provider_agent)

    logger.info(
        "garage_layout_by_provider_started provider_agent=%s provider_url=%s",
        provider_agent,
        provider["url"],
    )

    return get_provider_garage_layout(provider["url"])

def _decimal_or_none(value) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def call_provider_search(
    provider: dict,
    request_id: str,
    level_name: str | None = None,
    ev_charger: bool | None = None,
    handicap: bool | None = None,
    max_hourly_rate: Decimal | None = None,
    budget_amount: Decimal | None = None,
    budget_unit: str | None = None,
    duration_minutes: int | None = None,
    limit: int = 5,
) -> list[ProviderSlotResult]:
    params = {"level_name": level_name, "ev_charger": ev_charger, "handicap": handicap, "limit": limit}
    if max_hourly_rate is not None:
        params["max_hourly_rate"] = str(max_hourly_rate)
    if budget_amount is not None:
        params["budget_amount"] = str(budget_amount)
    if budget_unit:
        params["budget_unit"] = budget_unit
    if duration_minutes:
        params["duration_minutes"] = duration_minutes
    payload = {"jsonrpc": "2.0", "id": request_id, "method": "search_slots", "params": params}
    logger.info("provider_search_started provider=%s url=%s", provider.get("name"), provider.get("url"))
    logger.debug("provider_search_payload=%s", payload)
    response = post_a2a(url=f"{provider['url'].rstrip('/')}/a2a", payload=payload, verify_tls=get_httpx_verify_tls())
    if response.get("error"):
        raise RuntimeError(response["error"]["message"])
    slots = response["result"]["slots"]
    logger.info("provider_search_completed provider=%s count=%s", provider.get("name"), len(slots))
    return [
        ProviderSlotResult(
            provider_agent=provider["name"],
            provider_url=provider["url"],
            slot_code=slot["slot_code"],
            level_name=slot["level_name"],
            slot_type=slot["slot_type"],
            status=slot["status"],
            hourly_rate=_decimal_or_none(slot.get("hourly_rate")),
            daily_rate=_decimal_or_none(slot.get("daily_rate")),
            monthly_rate=_decimal_or_none(slot.get("monthly_rate")),
            estimated_price=_decimal_or_none(slot.get("estimated_price")),
            estimated_price_unit=slot.get("estimated_price_unit"),
            distance_to_entrance_meters=slot["distance_to_entrance_meters"],
            ev_charger=slot["ev_charger"],
            handicap=slot["handicap"],
        ) for slot in slots
    ]


def find_parking(
    level_name: str | None = None,
    ev_charger: bool | None = None,
    handicap: bool | None = None,
    max_hourly_rate: Decimal | None = None,
    budget_amount: Decimal | None = None,
    budget_unit: str | None = None,
    duration_minutes: int | None = None,
    limit_per_provider: int = 5,
) -> list[ProviderSlotResult]:
    providers = discover_search_agents()
    all_slots: list[ProviderSlotResult] = []
    with ThreadPoolExecutor(max_workers=max(1, len(providers))) as executor:
        futures = [executor.submit(call_provider_search, provider, f"host-search-{provider['name']}", level_name, ev_charger, handicap, max_hourly_rate, budget_amount, budget_unit, duration_minutes, limit_per_provider) for provider in providers]
        for future in as_completed(futures):
            all_slots.extend(future.result())
    return sorted(all_slots, key=lambda slot: (slot.estimated_price if slot.estimated_price is not None else slot.hourly_rate or Decimal("999999"), slot.distance_to_entrance_meters))


def get_provider_garage_layout(provider_url: str) -> dict:
    payload = {"jsonrpc": "2.0", "id": "host-get-garage-layout", "method": "get_garage_layout", "params": {}}
    logger.info("garage_layout_started provider_url=%s", provider_url)
    response = post_a2a(url=f"{provider_url.rstrip('/')}/a2a", payload=payload, verify_tls=get_httpx_verify_tls())
    if response.get("error"):
        raise RuntimeError(response["error"]["message"])
    return response["result"]


def hold_parking_slot(provider_url: str, slot_code: str, user_id: str, hold_minutes: int = 5) -> dict:
    payload = {"jsonrpc": "2.0", "id": f"host-hold-{slot_code}", "method": "hold_slot", "params": {"slot_code": slot_code, "user_id": user_id, "hold_minutes": hold_minutes}}
    logger.info("provider_hold_started provider_url=%s slot_code=%s user_id=%s", provider_url, slot_code, user_id)
    logger.debug("provider_hold_payload=%s", payload)
    response = post_a2a(url=f"{provider_url.rstrip('/')}/a2a", payload=payload, verify_tls=get_httpx_verify_tls())
    if response.get("error"):
        raise RuntimeError(response["error"]["message"])
    logger.info("provider_hold_completed slot_code=%s hold_id=%s", slot_code, response["result"].get("hold_id"))
    return response["result"]


def confirm_parking_reservation(provider_url: str, hold_id: str, user_id: str, reserved_minutes: int = 60) -> dict:
    payload = {"jsonrpc": "2.0", "id": f"host-confirm-{hold_id}", "method": "confirm_reservation", "params": {"hold_id": hold_id, "user_id": user_id, "reserved_minutes": reserved_minutes}}
    logger.info("provider_confirm_started provider_url=%s hold_id=%s user_id=%s", provider_url, hold_id, user_id)
    logger.debug("provider_confirm_payload=%s", payload)
    response = post_a2a(url=f"{provider_url.rstrip('/')}/a2a", payload=payload, verify_tls=get_httpx_verify_tls())
    if response.get("error"):
        raise RuntimeError(response["error"]["message"])
    logger.info("provider_confirm_completed hold_id=%s reservation_id=%s", hold_id, response["result"].get("reservation_id"))
    return response["result"]


def cancel_parking_hold(provider_url: str, hold_id: str, user_id: str) -> dict:
    payload = {"jsonrpc": "2.0", "id": f"host-cancel-{hold_id}", "method": "cancel_hold", "params": {"hold_id": hold_id, "user_id": user_id}}
    logger.info("provider_cancel_hold_started provider_url=%s hold_id=%s", provider_url, hold_id)
    response = post_a2a(url=f"{provider_url.rstrip('/')}/a2a", payload=payload, verify_tls=get_httpx_verify_tls())
    if response.get("error"):
        raise RuntimeError(response["error"]["message"])
    return response["result"]


def release_parking_slot(provider_url: str, slot_code: str, user_id: str, reason: str | None = None) -> dict:
    payload = {"jsonrpc": "2.0", "id": f"host-release-{slot_code}", "method": "release_slot", "params": {"slot_code": slot_code, "user_id": user_id, "reason": reason}}
    logger.info("provider_release_started provider_url=%s slot_code=%s", provider_url, slot_code)
    response = post_a2a(url=f"{provider_url.rstrip('/')}/a2a", payload=payload, verify_tls=get_httpx_verify_tls())
    if response.get("error"):
        raise RuntimeError(response["error"]["message"])
    return response["result"]
