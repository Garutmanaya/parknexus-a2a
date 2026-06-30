"""
ORM models for ParkNexus A2A platform database.

The platform DB stores registry metadata, users, and user-facing transactions.
Provider-owned parking databases remain isolated and own actual slot state.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from platform_services.registry_agent.base import PlatformBase


def utc_now() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class RegisteredAgentModel(PlatformBase):
    """Persisted provider Agent Card metadata."""

    __tablename__ = "registered_agents"

    registry_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UserAccountModel(PlatformBase):
    """Platform user account created by admin UI.

    Passwords are stored as hashes only. The local project uses a simple
    salted SHA-256 hash in user_service.py to avoid adding another dependency.
    Production should replace this with Cognito/OIDC or a dedicated identity
    provider.
    """

    __tablename__ = "user_accounts"

    user_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UserTransactionModel(PlatformBase):
    """User-facing transaction history persisted at Host/platform layer."""

    __tablename__ = "user_transactions"

    transaction_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_agent: Mapped[str | None] = mapped_column(String(150), nullable=True)
    provider_url: Mapped[str] = mapped_column(String(500), nullable=False)
    slot_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hold_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reservation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


Index("idx_registered_agents_name", RegisteredAgentModel.name)
Index("idx_registered_agents_active", RegisteredAgentModel.is_active)
Index("idx_user_accounts_email", UserAccountModel.email)
Index("idx_user_transactions_user_time", UserTransactionModel.user_id, UserTransactionModel.created_at)
Index("idx_user_transactions_status", UserTransactionModel.status)


if __name__ == "__main__":
    print("Platform models loaded:")
    for table_name in PlatformBase.metadata.tables:
        print(f"- {table_name}")
