"""
ORM models for ParkNexus A2A platform registry database.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column


from platform_services.registry_agent.base import PlatformBase

def utc_now() -> datetime:
    """
    Return timezone-aware UTC timestamp.
    """
    return datetime.now(timezone.utc)


class RegisteredAgentModel(PlatformBase):
    """
    Persisted provider Agent Card metadata.
    """

    __tablename__ = "registered_agents"

    registry_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

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


Index("idx_registered_agents_name", RegisteredAgentModel.name)
Index("idx_registered_agents_active", RegisteredAgentModel.is_active)


if __name__ == "__main__":
    """
    Manual test:
        python -m platform_services.registry_agent.models
    """
    print("Platform registry models loaded:")
    for table_name in PlatformBase.metadata.tables:
        print(f"- {table_name}")
