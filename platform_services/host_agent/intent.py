"""
LLM structured intent parser for ParkNexus Host Agent.

User natural language is converted into a validated ParkingIntent schema.
Provider agents never receive raw natural language.
"""

import os
from decimal import Decimal
from enum import Enum
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from shared.logging.logger import get_logger

logger = get_logger(__name__)

class BudgetUnit(str, Enum):
    HOUR = "hour"
    DAY = "day"
    MONTH = "month"
    TOTAL = "total"
    UNKNOWN = "unknown"


class ParkingIntent(BaseModel):
    intent: Literal["search_parking", "reserve_parking", "clarify"] = "search_parking"

    level_name: str | None = Field(
        default=None,
        description="Garage level preference, for example GROUND, ROOFTOP, BASEMENT_1.",
    )
    slot_type: str | None = Field(default=None)
    ev_charger: bool | None = Field(default=None)
    handicap: bool | None = Field(default=None)

    budget_amount: Decimal | None = Field(default=None)
    budget_unit: BudgetUnit = BudgetUnit.UNKNOWN

    duration_minutes: int | None = Field(default=None)
    sort_by: list[Literal["price", "distance", "ev", "accessibility"]] = Field(
        default_factory=lambda: ["price", "distance"]
    )

    wants_reservation: bool = False
    clarification_question: str | None = None


def get_openai_client() -> OpenAI:
    """
    Create OpenAI client from environment.
    """
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for LLM intent parsing")

    return OpenAI()


def get_intent_model() -> str:
    """
    Host intent parser model.
    """
    load_dotenv()
    return os.getenv("HOST_INTENT_MODEL", "gpt-4.1-mini")


def parse_user_request(user_text: str) -> ParkingIntent:
    """
    Parse user natural language into structured parking intent.
    """
    client = get_openai_client()

    response = client.responses.parse(
        model=get_intent_model(),
        instructions=(
            "You are the intent parser for ParkNexus A2A parking platform. "
            "Extract only structured parking intent. "
            "Do not invent unavailable details. "
            "If the user request is too ambiguous to search, set intent='clarify' "
            "and provide clarification_question. "
            "Normalize common level names: ground -> GROUND, rooftop -> ROOFTOP, "
            "basement -> BASEMENT_1. "
            "For budget, preserve unit exactly as hour, day, month, total, or unknown."
        ),
        input=user_text,
        text_format=ParkingIntent,
    )

    return response.output_parsed


def normalize_provider_search_params(intent: ParkingIntent) -> dict:
    """
    Convert Host-level intent into provider search_slots params.

    Current provider DB supports hourly price only.
    For non-hour budget units, do not force incorrect conversion.
    """
    max_price_per_hour = None

    if intent.budget_amount is not None and intent.budget_unit == BudgetUnit.HOUR:
        max_price_per_hour = str(intent.budget_amount)

    return {
        "level_name": intent.level_name,
        "slot_type": intent.slot_type,
        "ev_charger": intent.ev_charger,
        "handicap": intent.handicap,
        "max_price_per_hour": max_price_per_hour,
        "limit": 5,
    }


if __name__ == "__main__":
    samples = [
        "Find me a cheap ground level EV parking slot under $15 per hour",
        "Find me parking under $15 per day",
        "I need accessible parking close to entrance",
    ]

    for sample in samples:
        print(sample)
        print(parse_user_request(sample).model_dump())
        print()
