"""
Provider database utilities for ParkNexus A2A.

Each provider agent owns its own PostgreSQL database and user.

This module creates SQLAlchemy engines and sessions dynamically from
resolved provider agent configuration.

No provider database credentials are hardcoded.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

import agent_runtime.models  
from sqlalchemy.orm import Session, sessionmaker
from agent_runtime.base import Base

from shared.logging.logger import get_logger

logger = get_logger(__name__)

def build_provider_database_url(agent_config: dict) -> str:
    """
    Build SQLAlchemy database URL from resolved provider config.

    Args:
        agent_config: Resolved config from config_loader.load_agent_config().

    Returns:
        PostgreSQL SQLAlchemy connection URL.
    """
    database = agent_config["database"]

    host = agent_config.get("postgres_host")
    port = agent_config.get("postgres_port")

    if not host or not port:
        raise RuntimeError(
            "agent_config must include postgres_host and postgres_port. "
            "Make sure config_loader resolves them from .env."
        )

    return (
        "postgresql+psycopg://"
        f"{database['db_user']}:{database['db_password']}"
        f"@{host}:{port}/{database['db_name']}"
    )


def create_provider_engine(agent_config: dict) -> Engine:
    """
    Create SQLAlchemy engine for a provider-owned database.
    """
    return create_engine(
        build_provider_database_url(agent_config),
        echo=False,
        pool_pre_ping=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker:
    """
    Create SQLAlchemy session factory for a provider database.
    """
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )


def create_tables(engine: Engine) -> None:
    """
    Create all provider tables if they do not already exist.
    """
    Base.metadata.create_all(bind=engine)


def verify_connection(engine: Engine) -> None:
    """
    Verify provider database connection.
    """
    with engine.connect() as conn:
        row = conn.execute(text("SELECT current_database(), current_user")).fetchone()

    print("Provider ORM DB connection verified")
    print(f"Database: {row[0]}")
    print(f"User: {row[1]}")


def get_db_dependency(session_factory: sessionmaker):
    """
    Build FastAPI DB dependency for a specific provider session factory.

    Usage:
        get_db = get_db_dependency(SessionLocal)
    """

    def get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    return get_db


if __name__ == "__main__":
    """
    Manual test:
        python -m agent_runtime.database --config agents/company_a/agent.yaml
    """
    import argparse

    import agent_runtime.models  # noqa: F401
    from agent_runtime.config_loader import load_agent_config
    from agent_runtime.bootstrap import bootstrap_provider_database

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to provider agent.yaml")
    args = parser.parse_args()

    config = load_agent_config(args.config)

    bootstrap_provider_database(config)

    engine = create_provider_engine(config)
    verify_connection(engine)

    create_tables(engine)
    print("Provider ORM tables created successfully")

    print("Registered tables:")
    for table_name in Base.metadata.tables:
        print(f"- {table_name}")
