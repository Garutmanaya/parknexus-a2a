"""LLM structured intent parser for ParkNexus Host Agent."""

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
    level_name: str | None = Field(default=None, description="Garage level preference, for example GROUND, ROOFTOP, BASEMENT_1.")
    slot_type: str | None = None
    ev_charger: bool | None = None
    handicap: bool | None = None
    budget_amount: Decimal | None = None
    budget_unit: BudgetUnit = BudgetUnit.UNKNOWN
    duration_minutes: int | None = None
    sort_by: list[Literal["price", "distance", "ev", "accessibility"]] = Field(default_factory=lambda: ["price", "distance"])
    wants_reservation: bool = False
    clarification_question: str | None = None


def get_openai_client() -> OpenAI:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for LLM intent parsing")
    return OpenAI()


def get_intent_model() -> str:
    load_dotenv()
    return os.getenv("HOST_INTENT_MODEL", "gpt-4.1-mini")


def parse_user_request(user_text: str) -> ParkingIntent:
    logger.info("intent_parse_started")
    logger.debug("intent_parse_input=%s", user_text)
    client = get_openai_client()
    response = client.responses.parse(
        model=get_intent_model(),
        instructions=(
            "You are the intent parser for ParkNexus A2A parking platform. "
            "Extract only structured parking intent. Do not invent unavailable details. "
            "If the request is too ambiguous to search or reserve, set intent='clarify' and provide clarification_question. "
            "Normalize common level names: ground -> GROUND, rooftop -> ROOFTOP, basement -> BASEMENT_1. "
            "For budget, preserve unit exactly as hour, day, month, total, or unknown. "
            "If the user asks to book/reserve/hold, set wants_reservation=true."
        ),
        input=user_text,
        text_format=ParkingIntent,
    )
    intent = response.output_parsed
    logger.info("intent_parse_completed intent=%s", intent.intent)
    logger.debug("intent_parse_result=%s", intent.model_dump())
    return intent


if __name__ == "__main__":
    for sample in ["Find me a cheap ground level EV parking slot under $15 per hour", "Find me parking under $15 per day", "I need accessible parking close to entrance"]:
        print(sample)
        print(parse_user_request(sample).model_dump())
