"""
Config-driven seed logic for ParkNexus A2A provider agents.

This module reads garage layout from agent.yaml and creates:
- provider metadata
- garage metadata
- parking slots

Each provider can have a different garage shape without code changes.
"""

import argparse
from decimal import Decimal

import agent_runtime.models  # noqa: F401
from agent_runtime.bootstrap import bootstrap_provider_database
from agent_runtime.config_loader import load_agent_config
from agent_runtime.database import create_provider_engine, create_session_factory, create_tables
from agent_runtime.models import Garage, ParkingSlot, Provider, SlotStatus, SlotType

from shared.logging.logger import get_logger

logger = get_logger(__name__)

def parse_slot_ref(slot_ref: str) -> tuple[str, str, int]:
    """
    Parse slot reference from config.

    Format:
        LEVEL:ROW:COLUMN

    Example:
        GROUND:A:3
    """
    level_name, row_label, column_number = slot_ref.split(":")
    return level_name, row_label, int(column_number)


def get_or_create_provider(db, agent_config: dict) -> Provider:
    """
    Create provider metadata if missing.
    """
    provider = (
        db.query(Provider)
        .filter(Provider.agent_id == agent_config["agent_id"])
        .first()
    )

    if provider:
        return provider

    provider = Provider(
        agent_id=agent_config["agent_id"],
        display_name=agent_config["display_name"],
        description=agent_config.get("description"),
        is_active=True,
    )

    db.add(provider)
    db.flush()

    return provider


def get_or_create_garage(db, provider: Provider, agent_config: dict) -> Garage:
    """
    Create garage metadata if missing.
    """
    garage_config = agent_config["garage"]

    garage = (
        db.query(Garage)
        .filter(
            Garage.provider_id == provider.provider_id,
            Garage.name == garage_config["name"],
        )
        .first()
    )

    if garage:
        return garage

    garage = Garage(
        provider_id=provider.provider_id,
        name=garage_config["name"],
        address=garage_config["address"],
        city=garage_config["city"],
        state=garage_config["state"],
        postal_code=str(garage_config["postal_code"]),
        is_active=True,
    )

    db.add(garage)
    db.flush()

    return garage


def resolve_pricing(agent_config: dict, level_name: str) -> tuple[Decimal, Decimal | None, Decimal | None]:
    """
    Resolve hourly, daily, and monthly pricing for a slot.
    """
    pricing = agent_config.get("pricing", {})
    by_level = pricing.get("by_level", {})
    level_pricing = by_level.get(level_name, {})

    if isinstance(level_pricing, dict):
        hourly = level_pricing.get("hourly_rate", pricing.get("default_price_per_hour", 10.0))
        daily = level_pricing.get("daily_rate", pricing.get("default_daily_rate"))
        monthly = level_pricing.get("monthly_rate", pricing.get("default_monthly_rate"))
    else:
        hourly = level_pricing
        daily = pricing.get("default_daily_rate")
        monthly = pricing.get("default_monthly_rate")

    return (
        Decimal(str(hourly)),
        Decimal(str(daily)) if daily is not None else None,
        Decimal(str(monthly)) if monthly is not None else None,
    )


def resolve_slot_features(
    agent_config: dict,
    level_name: str,
    row_label: str,
    column_number: int,
) -> tuple[SlotType, bool, bool]:
    """
    Resolve slot type and feature flags from config.
    """
    features = agent_config.get("features", {})

    ev_slots = {
        parse_slot_ref(slot_ref)
        for slot_ref in features.get("ev_slots", [])
    }

    handicap_slots = {
        parse_slot_ref(slot_ref)
        for slot_ref in features.get("handicap_slots", [])
    }

    current_slot = (level_name, row_label, column_number)

    ev_charger = current_slot in ev_slots
    handicap = current_slot in handicap_slots

    if handicap:
        slot_type = SlotType.HANDICAP
    elif ev_charger:
        slot_type = SlotType.EV
    else:
        slot_type = SlotType.STANDARD

    return slot_type, ev_charger, handicap


def slot_exists(db, slot_code: str) -> bool:
    """
    Check whether slot already exists.
    """
    return (
        db.query(ParkingSlot)
        .filter(ParkingSlot.slot_code == slot_code)
        .first()
        is not None
    )


def generate_slot_code(
    agent_id: str,
    level_name: str,
    row_label: str,
    column_number: int,
) -> str:
    """
    Generate deterministic slot code.

    Example:
        COMPANY_A-GROUND-A001
    """
    return f"{agent_id.upper()}-{level_name}-{row_label}{column_number:03d}"


def seed_slots(db, garage: Garage, agent_config: dict) -> int:
    """
    Generate parking slots from layout config.
    """
    inserted_count = 0
    layout = agent_config["layout"]

    for level in layout["levels"]:
        level_name = level["name"]
        
        hourly_rate, daily_rate, monthly_rate = resolve_pricing(agent_config, level_name)

        for row in level["rows"]:
            row_label = row["label"]
            columns = int(row["columns"])

            for column_number in range(1, columns + 1):
                slot_code = generate_slot_code(
                    agent_id=agent_config["agent_id"],
                    level_name=level_name,
                    row_label=row_label,
                    column_number=column_number,
                )

                if slot_exists(db, slot_code):
                    continue

                slot_type, ev_charger, handicap = resolve_slot_features(
                    agent_config=agent_config,
                    level_name=level_name,
                    row_label=row_label,
                    column_number=column_number,
                )

                slot = ParkingSlot(
                    garage_id=garage.garage_id,
                    slot_code=slot_code,
                    level_name=level_name,
                    row_label=row_label,
                    column_number=column_number,
                    slot_type=slot_type,
                    status=SlotStatus.AVAILABLE,
                    price_per_hour=hourly_rate,
                    daily_rate=daily_rate,
                    monthly_rate=monthly_rate,
                    distance_to_entrance_meters=50 + column_number * 4,
                    ev_charger=ev_charger,
                    handicap=handicap,
                )

                db.add(slot)
                inserted_count += 1

    return inserted_count


def seed_provider_database(agent_config: dict) -> None:
    """
    Bootstrap DB, create tables, and seed provider garage inventory.
    """
    bootstrap_provider_database(agent_config)

    engine = create_provider_engine(agent_config)
    create_tables(engine)

    SessionLocal = create_session_factory(engine)
    db = SessionLocal()

    try:
        provider = get_or_create_provider(db, agent_config)
        garage = get_or_create_garage(db, provider, agent_config)
        inserted_count = seed_slots(db, garage, agent_config)

        db.commit()

        print("Provider seed completed successfully")
        print(f"agent_id={agent_config['agent_id']}")
        print(f"garage={garage.name}")
        print(f"new_slots_inserted={inserted_count}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    """
    Manual test:
        python -m agent_runtime.seed --config agents/company_a/agent.yaml
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to provider agent.yaml")
    args = parser.parse_args()

    config = load_agent_config(args.config)
    seed_provider_database(config)
