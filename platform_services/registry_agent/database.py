"""
Platform database utilities for ParkNexus A2A Registry Agent.

The platform DB stores registry metadata only.
Provider-owned parking databases remain isolated.
"""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


from sqlalchemy.orm import Session, sessionmaker
from platform_services.registry_agent.base import PlatformBase

from agent_runtime.bootstrap import (
    build_admin_database_url,
    create_admin_engine,
    create_database_if_missing,
    create_role_if_missing,
    grant_database_privileges,
    grant_schema_privileges,
)
import platform_services.registry_agent.models  # noqa: F401
from shared.logging.logger import get_logger

logger = get_logger(__name__)


def required_env(name: str) -> str:
    """
    Read required environment variable.
    """
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")

    return value


def load_platform_db_config() -> dict:
    """
    Load platform database configuration from .env.
    """
    load_dotenv()

    return {
        "host": required_env("POSTGRES_HOST"),
        "port": required_env("POSTGRES_PORT"),
        "db_name": required_env("PLATFORM_DB_NAME"),
        "db_user": required_env("PLATFORM_DB_USER"),
        "db_password": required_env("PLATFORM_DB_PASSWORD"),
    }


def build_platform_database_url() -> str:
    """
    Build platform DB SQLAlchemy URL.
    """
    config = load_platform_db_config()

    return (
        "postgresql+psycopg://"
        f"{config['db_user']}:{config['db_password']}"
        f"@{config['host']}:{config['port']}/{config['db_name']}"
    )


def bootstrap_platform_database() -> None:
    """
    Create platform DB and platform DB user if missing.
    """
    config = load_platform_db_config()
    admin_engine = create_admin_engine()

    create_database_if_missing(admin_engine, config["db_name"])
    create_role_if_missing(admin_engine, config["db_user"], config["db_password"])
    grant_database_privileges(admin_engine, config["db_name"], config["db_user"])
    grant_schema_privileges(
        db_name=config["db_name"],
        db_user=config["db_user"],
        db_password=config["db_password"],
    )

    logger.info("platform_database_bootstrap_completed")


def create_platform_engine():
    """
    Create SQLAlchemy engine for platform DB.
    """
    return create_engine(
        build_platform_database_url(),
        echo=False,
        pool_pre_ping=True,
    )


platform_engine = create_platform_engine()

PlatformSessionLocal = sessionmaker(
    bind=platform_engine,
    autoflush=False,
    autocommit=False,
)


def create_platform_tables() -> None:
    """
    Create platform database tables and apply safe local-dev additive upgrades.

    SQLAlchemy create_all() does not alter existing tables. These ALTER statements
    keep the project convenient while the schema is still evolving locally.
    Production should use Alembic migrations instead.
    """
    import platform_services.registry_agent.models  # noqa: F401

    PlatformBase.metadata.create_all(bind=platform_engine)
    apply_local_schema_upgrades()
    logger.info("platform_tables_created_successfully")


def apply_local_schema_upgrades() -> None:
    """Apply additive schema changes for local development."""
    statements = [
        "ALTER TABLE IF EXISTS user_accounts ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255) DEFAULT '' NOT NULL",
        "ALTER TABLE IF EXISTS user_accounts ADD COLUMN IF NOT EXISTS first_name VARCHAR(100)",
        "ALTER TABLE IF EXISTS user_accounts ADD COLUMN IF NOT EXISTS last_name VARCHAR(100)",
        "ALTER TABLE IF EXISTS user_accounts ADD COLUMN IF NOT EXISTS phone_number VARCHAR(50)",
        "ALTER TABLE IF EXISTS user_accounts ADD COLUMN IF NOT EXISTS address TEXT",
    ]
    with platform_engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def get_platform_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for platform database.
    """
    db = PlatformSessionLocal()

    try:
        yield db

    finally:
        db.close()


def verify_platform_connection() -> None:
    """
    Verify platform database connection.
    """
    with platform_engine.connect() as conn:
        row = conn.execute(text("SELECT current_database(), current_user")).fetchone()

    print("Platform DB connection verified")
    print(f"Database: {row[0]}")
    print(f"User: {row[1]}")


if __name__ == "__main__":
    """
    Manual test:
        python -m platform_services.registry_agent.database
    """
    bootstrap_platform_database()
    verify_platform_connection()
    create_platform_tables()
