"""Pydantic API schemas for ParkNexus A2A provider runtime."""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field


class ParkingSlotResponse(BaseModel):
    slot_id: str
    garage_id: str
    slot_code: str
    level_name: str
    row_label: str
    column_number: int
    slot_type: str
    status: str
    hourly_rate: Decimal
    daily_rate: Decimal | None = None
    monthly_rate: Decimal | None = None
    distance_to_entrance_meters: int
    ev_charger: bool
    handicap: bool
    model_config = ConfigDict(from_attributes=True)


class SlotSearchRequest(BaseModel):
    level_name: str | None = None
    slot_type: str | None = None
    ev_charger: bool | None = None
    handicap: bool | None = None
    max_hourly_rate: Decimal | None = None
    budget_amount: Decimal | None = None
    budget_unit: str | None = None
    duration_minutes: int | None = None
    limit: int = 50


class SlotSearchResponse(BaseModel):
    count: int
    slots: list[ParkingSlotResponse]


class HoldSlotRequest(BaseModel):
    slot_code: str
    user_id: str
    hold_minutes: int = 5


class HoldSlotResponse(BaseModel):
    hold_id: str
    slot_id: str
    slot_code: str
    user_id: str
    status: str
    expires_at: datetime


class ConfirmReservationRequest(BaseModel):
    hold_id: str
    user_id: str
    reserved_minutes: int = 60


class ReservationResponse(BaseModel):
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
    hold_id: str
    user_id: str


class ReleaseSlotRequest(BaseModel):
    slot_code: str
    user_id: str
    reason: str | None = None


class WorkflowResponse(BaseModel):
    status: str
    message: str
    slot_code: str | None = None


class A2ARequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict = Field(default_factory=dict)


class A2AResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    result: dict | None = None
    error: dict | None = None


class A2AStreamEvent(BaseModel):
    event: str
    data: dict
