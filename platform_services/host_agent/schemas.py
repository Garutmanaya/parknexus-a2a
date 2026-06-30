"""
Pydantic schemas for ParkNexus A2A Host Agent.
"""

from decimal import Decimal

from pydantic import BaseModel

from shared.logging.logger import get_logger

logger = get_logger(__name__)

class FindParkingRequest(BaseModel):
    """
    User-facing parking search request.
    """

    level_name: str | None = None
    ev_charger: bool | None = None
    handicap: bool | None = None
    max_price_per_hour: Decimal | None = None
    limit_per_provider: int = 5


class ProviderSlotResult(BaseModel):
    """
    Slot returned by a provider agent.
    """

    provider_agent: str
    provider_url: str
    slot_code: str
    level_name: str
    slot_type: str
    status: str
    price_per_hour: Decimal
    distance_to_entrance_meters: int
    ev_charger: bool
    handicap: bool


class FindParkingResponse(BaseModel):
    """
    Aggregated Host Agent search response.
    """

    count: int
    slots: list[ProviderSlotResult]

class ChatParkingRequest(BaseModel):
    """
    Natural language parking request.
    """

    message: str


class ChatParkingResponse(BaseModel):
    """
    Host Agent natural language response.
    """

    intent: dict
    count: int
    slots: list[ProviderSlotResult]
    

class HoldParkingRequest(BaseModel):
    provider_url: str
    slot_code: str
    user_id: str
    hold_minutes: int = 5


class ConfirmParkingRequest(BaseModel):
    provider_url: str
    hold_id: str
    user_id: str
    reserved_minutes: int = 60


class CancelHoldRequest(BaseModel):
    provider_url: str
    hold_id: str
    user_id: str


class ReleaseSlotRequest(BaseModel):
    provider_url: str
    slot_code: str
    user_id: str
    reason: str | None = None


