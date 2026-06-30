"""
ORM models for a provider-owned ParkNexus A2A parking database.

Each provider database contains its own:
- provider metadata
- garage
- parking slots
- holds
- reservations
- slot events

These models are used by every provider agent runtime, but each runtime
connects to a separate provider-owned database.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agent_runtime.base import Base

from shared.logging.logger import get_logger

logger = get_logger(__name__)

def utc_now() -> datetime:
    """
    Return timezone-aware UTC timestamp.
    """
    return datetime.now(timezone.utc)


class SlotStatus(str, enum.Enum):
    """
    Parking slot lifecycle status.
    """

    AVAILABLE = "AVAILABLE"
    HELD = "HELD"
    RESERVED = "RESERVED"
    OCCUPIED = "OCCUPIED"
    RELEASED = "RELEASED"
    BLOCKED = "BLOCKED"
    MAINTENANCE = "MAINTENANCE"


class SlotType(str, enum.Enum):
    """
    Parking slot category.
    """

    STANDARD = "STANDARD"
    EV = "EV"
    HANDICAP = "HANDICAP"
    COMPACT = "COMPACT"
    VIP = "VIP"


class ReservationStatus(str, enum.Enum):
    """
    Hold and reservation lifecycle status.
    """

    HELD = "HELD"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"


class Provider(Base):
    """
    Provider metadata stored inside provider-owned database.

    This keeps the provider DB self-describing.
    """

    __tablename__ = "providers"

    provider_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    agent_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    garages: Mapped[list["Garage"]] = relationship(back_populates="provider")


class Garage(Base):
    """
    Provider-owned parking garage.

    For now each agent config seeds one garage.
    Later one provider can own multiple garages.
    """

    __tablename__ = "garages"

    garage_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    provider_id: Mapped[str] = mapped_column(
        ForeignKey("providers.provider_id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    provider: Mapped["Provider"] = relationship(back_populates="garages")
    slots: Mapped[list["ParkingSlot"]] = relationship(back_populates="garage")


class ParkingSlot(Base):
    """
    Individual parking slot.

    Supports arbitrary layouts because slots are generated from agent.yaml.
    """

    __tablename__ = "parking_slots"

    slot_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    garage_id: Mapped[str] = mapped_column(
        ForeignKey("garages.garage_id"),
        nullable=False,
    )

    slot_code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    level_name: Mapped[str] = mapped_column(String(50), nullable=False)
    row_label: Mapped[str] = mapped_column(String(20), nullable=False)
    column_number: Mapped[int] = mapped_column(Integer, nullable=False)

    slot_type: Mapped[SlotType] = mapped_column(Enum(SlotType), nullable=False)
    status: Mapped[SlotStatus] = mapped_column(
        Enum(SlotStatus),
        default=SlotStatus.AVAILABLE,
        nullable=False,
    )

    price_per_hour: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    daily_rate: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    monthly_rate: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    distance_to_entrance_meters: Mapped[int] = mapped_column(Integer, nullable=False)

    ev_charger: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    handicap: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    garage: Mapped["Garage"] = relationship(back_populates="slots")


class SlotHold(Base):
    """
    Temporary slot hold before reservation confirmation.
    """

    __tablename__ = "slot_holds"

    hold_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    slot_id: Mapped[str] = mapped_column(
        ForeignKey("parking_slots.slot_id"),
        nullable=False,
    )

    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus),
        default=ReservationStatus.HELD,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Reservation(Base):
    """
    Confirmed parking reservation.
    """

    __tablename__ = "reservations"

    reservation_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    slot_id: Mapped[str] = mapped_column(
        ForeignKey("parking_slots.slot_id"),
        nullable=False,
    )
    hold_id: Mapped[str | None] = mapped_column(
        ForeignKey("slot_holds.hold_id"),
        nullable=True,
    )

    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus),
        default=ReservationStatus.CONFIRMED,
        nullable=False,
    )

    reserved_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reserved_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SlotEvent(Base):
    """
    Append-only audit trail for slot lifecycle changes.
    """

    __tablename__ = "slot_events"

    event_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    slot_id: Mapped[str] = mapped_column(
        ForeignKey("parking_slots.slot_id"),
        nullable=False,
    )

    old_status: Mapped[SlotStatus | None] = mapped_column(Enum(SlotStatus), nullable=True)
    new_status: Mapped[SlotStatus] = mapped_column(Enum(SlotStatus), nullable=False)

    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


Index("idx_slots_garage_status", ParkingSlot.garage_id, ParkingSlot.status)
Index("idx_slots_filters", ParkingSlot.level_name, ParkingSlot.slot_type, ParkingSlot.status)
Index("idx_holds_slot_status", SlotHold.slot_id, SlotHold.status)
Index("idx_reservations_slot_status", Reservation.slot_id, Reservation.status)
Index("idx_slot_events_slot_time", SlotEvent.slot_id, SlotEvent.created_at)


if __name__ == "__main__":
    """
    Manual schema inspection:
        python -m agent_runtime.models
    """
    print("Loaded provider ORM models:")
    for table_name in Base.metadata.tables:
        print(f"- {table_name}")
