"""
SQLAlchemy declarative base for ParkNexus A2A provider runtime.

This file exists to avoid circular imports between:
- database.py
- models.py
"""

from sqlalchemy.orm import DeclarativeBase

from shared.logging.logger import get_logger

logger = get_logger(__name__)

class Base(DeclarativeBase):
    """
    Base class for all provider ORM models.
    """

    pass
