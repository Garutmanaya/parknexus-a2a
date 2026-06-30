"""Pydantic schemas for ParkNexus A2A Host Agent."""

from decimal import Decimal
from pydantic import BaseModel


class FindParkingRequest(BaseModel):
    level_name: str | None = None
    ev_charger: bool | None = None
    handicap: bool | None = None
    max_hourly_rate: Decimal | None = None
    budget_amount: Decimal | None = None
    budget_unit: str | None = None
    duration_minutes: int | None = None
    limit_per_provider: int = 5


class ProviderSlotResult(BaseModel):
    provider_agent: str
    provider_url: str
    slot_code: str
    level_name: str
    slot_type: str
    status: str
    hourly_rate: Decimal | None = None
    daily_rate: Decimal | None = None
    monthly_rate: Decimal | None = None
    estimated_price: Decimal | None = None
    estimated_price_unit: str | None = None
    distance_to_entrance_meters: int
    ev_charger: bool
    handicap: bool


class FindParkingResponse(BaseModel):
    count: int
    slots: list[ProviderSlotResult]


class ChatParkingRequest(BaseModel):
    message: str


class ChatParkingResponse(BaseModel):
    type: str | None = None
    intent: dict
    count: int
    slots: list[ProviderSlotResult]
    message: str | None = None


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


class GarageLayoutRequest(BaseModel):
    provider_url: str


class ProviderSummary(BaseModel):
    name: str
    url: str
    description: str | None = None
    provider: dict = {}
    capabilities: dict = {}
    skills: list[dict] = []


class ProvidersResponse(BaseModel):
    count: int
    providers: list[ProviderSummary]


class GarageLayoutByProviderRequest(BaseModel):
    provider_agent: str


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    authenticated: bool
    message: str


class UserLoginRequest(BaseModel):
    user_id: str
    password: str


class UserLoginResponse(BaseModel):
    authenticated: bool
    user: dict | None = None
    message: str


class CreateUserRequest(BaseModel):
    user_id: str
    password: str
    email: str
    display_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None
    address: str | None = None


class UpdateUserRequest(BaseModel):
    user_id: str
    password: str | None = None
    email: str | None = None
    display_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None
    address: str | None = None
    is_active: bool | None = None


class UserStatusRequest(BaseModel):
    user_id: str
    is_active: bool


class UserResponse(BaseModel):
    user_id: str
    display_name: str
    first_name: str | None = None
    last_name: str | None = None
    email: str
    phone_number: str | None = None
    address: str | None = None
    is_active: bool
    created_at: str | None = None
    updated_at: str | None = None


class AgentsResponse(BaseModel):
    count: int
    agents: list[dict]


class UsersResponse(BaseModel):
    count: int
    users: list[UserResponse]


class TransactionsResponse(BaseModel):
    count: int
    transactions: list[dict]
