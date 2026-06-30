"""
Service layer for ParkNexus A2A Host Agent.

Host Agent uses secure A2A for:
- Registry discovery
- Provider slot search
"""

from decimal import Decimal



from shared.config.runtime import (
    get_httpx_verify_tls,
    get_registry_agent_base_url,
)
from platform_services.host_agent.schemas import ProviderSlotResult
from shared.security.a2a_client import post_a2a

from shared.logging.logger import get_logger

logger = get_logger(__name__)

def discover_search_agents() -> list[dict]:
    """
    Discover provider agents through secure Registry A2A.
    """
    registry_url = get_registry_agent_base_url()

    payload = {
        "jsonrpc": "2.0",
        "id": "host-discover-search-agents",
        "method": "discover_agents",
        "params": {
            "skill_id": "search_slots",
            "streaming_required": True,
        },
    }

    response = post_a2a(
        url=f"{registry_url}/a2a",
        payload=payload,
        verify_tls=get_httpx_verify_tls(),
    )

    if response.get("error"):
        raise RuntimeError(response["error"]["message"])

    return response["result"]["agents"]


def call_provider_search(
    provider: dict,
    request_id: str,
    level_name: str | None = None,
    ev_charger: bool | None = None,
    handicap: bool | None = None,
    max_price_per_hour: Decimal | None = None,
    budget_amount: Decimal | None = None,
    budget_unit: str | None = None,
    duration_minutes: int | None = None,
    limit: int = 5,
) -> list[ProviderSlotResult]:
    """
    Call provider search_slots through secure A2A.
    """
    params = {
        "level_name": level_name,
        "ev_charger": ev_charger,
        "handicap": handicap,
        "limit": limit,
    }

    if max_price_per_hour is not None:
        params["max_price_per_hour"] = str(max_price_per_hour)
        
    if budget_amount is not None:
        params["budget_amount"] = str(budget_amount)

    if budget_unit:
        params["budget_unit"] = budget_unit

    if duration_minutes:
        params["duration_minutes"] = duration_minutes

    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "search_slots",
        "params": params,
    }

    response = post_a2a(
        url=f"{provider['url'].rstrip('/')}/a2a",
        payload=payload,
        verify_tls=get_httpx_verify_tls(),
    )

    if response.get("error"):
        raise RuntimeError(response["error"]["message"])

    slots = response["result"]["slots"]

    return [
        ProviderSlotResult(
            provider_agent=provider["name"],
            provider_url=provider["url"],
            slot_code=slot["slot_code"],
            level_name=slot["level_name"],
            slot_type=slot["slot_type"],
            status=slot["status"],
            price_per_hour=Decimal(slot["price_per_hour"]),
            distance_to_entrance_meters=slot["distance_to_entrance_meters"],
            ev_charger=slot["ev_charger"],
            handicap=slot["handicap"],
        )
        for slot in slots
    ]

def hold_parking_slot(
    provider_url: str,
    slot_code: str,
    user_id: str,
    hold_minutes: int = 5,
) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": f"host-hold-{slot_code}",
        "method": "hold_slot",
        "params": {
            "slot_code": slot_code,
            "user_id": user_id,
            "hold_minutes": hold_minutes,
        },
    }

    response = post_a2a(
        url=f"{provider_url.rstrip('/')}/a2a",
        payload=payload,
        verify_tls=get_httpx_verify_tls(),
    )

    if response.get("error"):
        raise RuntimeError(response["error"]["message"])

    return response["result"]


def confirm_parking_reservation(
    provider_url: str,
    hold_id: str,
    user_id: str,
    reserved_minutes: int = 60,
) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": f"host-confirm-{hold_id}",
        "method": "confirm_reservation",
        "params": {
            "hold_id": hold_id,
            "user_id": user_id,
            "reserved_minutes": reserved_minutes,
        },
    }

    response = post_a2a(
        url=f"{provider_url.rstrip('/')}/a2a",
        payload=payload,
        verify_tls=get_httpx_verify_tls(),
    )

    if response.get("error"):
        raise RuntimeError(response["error"]["message"])

    return response["result"]


def cancel_parking_hold(
    provider_url: str,
    hold_id: str,
    user_id: str,
) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": f"host-cancel-{hold_id}",
        "method": "cancel_hold",
        "params": {
            "hold_id": hold_id,
            "user_id": user_id,
        },
    }

    response = post_a2a(
        url=f"{provider_url.rstrip('/')}/a2a",
        payload=payload,
        verify_tls=get_httpx_verify_tls(),
    )

    if response.get("error"):
        raise RuntimeError(response["error"]["message"])

    return response["result"]


def release_parking_slot(
    provider_url: str,
    slot_code: str,
    user_id: str,
    reason: str | None = None,
) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": f"host-release-{slot_code}",
        "method": "release_slot",
        "params": {
            "slot_code": slot_code,
            "user_id": user_id,
            "reason": reason,
        },
    }

    response = post_a2a(
        url=f"{provider_url.rstrip('/')}/a2a",
        payload=payload,
        verify_tls=get_httpx_verify_tls(),
    )

    if response.get("error"):
        raise RuntimeError(response["error"]["message"])

    return response["result"]

def find_parking(
    level_name: str | None = None,
    ev_charger: bool | None = None,
    handicap: bool | None = None,
    max_price_per_hour: Decimal | None = None,
    limit_per_provider: int = 5,
) -> list[ProviderSlotResult]:
    """
    Find parking across all discovered providers.
    """
    providers = discover_search_agents()
    all_slots: list[ProviderSlotResult] = []

    for provider in providers:
        provider_slots = call_provider_search(
            provider=provider,
            request_id=f"host-search-{provider['name']}",
            level_name=level_name,
            ev_charger=ev_charger,
            handicap=handicap,
            max_price_per_hour=max_price_per_hour,
            limit=limit_per_provider,
        )
        all_slots.extend(provider_slots)

    return sorted(
        all_slots,
        key=lambda slot: (
            slot.price_per_hour,
            slot.distance_to_entrance_meters,
        ),
    )


if __name__ == "__main__":
    results = find_parking(limit_per_provider=3)
    print(f"Slots found: {len(results)}")
    for slot in results:
        print(slot.provider_agent, slot.slot_code, slot.price_per_hour)