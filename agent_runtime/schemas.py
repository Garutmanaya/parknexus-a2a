"""
Pydantic API schemas for ParkNexus A2A provider runtime.

These schemas define stable HTTP contracts for every provider agent.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from shared.logging.logger import get_logger

logger = get_logger(__name__)

class ParkingSlotResponse(BaseModel):
    """
    Parking slot response.
    """

    slot_id: str
    garage_id: str
    slot_code: str
    level_name: str
    row_label: str
    column_number: int
    slot_type: str
    status: str
    price_per_hour: Decimal
    distance_to_entrance_meters: int
    ev_charger: bool
    handicap: bool

    model_config = ConfigDict(from_attributes=True)


class SlotSearchRequest(BaseModel):
    """
    Search available slots.
    """

    level_name: str | None = None
    slot_type: str | None = None
    ev_charger: bool | None = None
    handicap: bool | None = None
    max_price_per_hour: Decimal | None = None
    limit: int = 50


class SlotSearchResponse(BaseModel):
    """
    Slot search response.
    """

    count: int
    slots: list[ParkingSlotResponse]


class HoldSlotRequest(BaseModel):
    """
    Hold an available slot.
    """

    slot_code: str
    user_id: str
    hold_minutes: int = 5


class HoldSlotResponse(BaseModel):
    """
    Slot hold response.
    """

    hold_id: str
    slot_id: str
    slot_code: str
    user_id: str
    status: str
    expires_at: datetime


class ConfirmReservationRequest(BaseModel):
    """
    Confirm a held slot.
    """

    hold_id: str
    user_id: str
    reserved_minutes: int = 60


class ReservationResponse(BaseModel):
    """
    Confirmed reservation response.
    """

    reservation_id: str
    hold_id: str | None
    slot_id: str
    slot_code: str
    user_id: str
    status: str
    reserved_from: datetime
    reserved_until: datetime
    total_price: Decimal


class CancelHoldRequest(BaseModel):
    """
    Cancel active hold.
    """

    hold_id: str
    user_id: str


class ReleaseSlotRequest(BaseModel):
    """
    Release a slot back to available.
    """

    slot_code: str
    user_id: str
    reason: str | None = None


class WorkflowResponse(BaseModel):
    """
    Generic workflow response.
    """

    status: str
    message: str
    slot_code: str | None = None



class A2ARequest(BaseModel):
    """
    Minimal JSON-RPC style A2A request.

    Example:
        {
          "jsonrpc": "2.0",
          "id": "req-001",
          "method": "search_slots",
          "params": {...}
        }
    """

    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict = {}


class A2AResponse(BaseModel):
    """
    Minimal JSON-RPC style A2A response.
    """

    jsonrpc: str = "2.0"
    id: str | int | None = None
    result: dict | None = None
    error: dict | None = None

class A2AStreamEvent(BaseModel):
    """
    A2A SSE event payload.
    """

    event: str
    data: dict

if __name__ == "__main__":
    """
    Manual test:
        python -m agent_runtime.schemas
    """
    sample = SlotSearchRequest(level_name="GROUND", limit=5)
    print("Schemas loaded successfully")
    print(sample.model_dump())
