"""
Dynamic database bootstrap for ParkNexus A2A provider agents.

This module creates provider-owned PostgreSQL resources at agent startup:

- provider database
- provider database user
- privileges for that user

Only admin credentials come from .env.
Provider database name/user/password are resolved from agent.yaml + .env.

Important:
    This is local/dev friendly and cloud-compatible as a startup bootstrap.
    In stricter production environments, DB/user creation may be moved to Terraform.
"""

import argparse
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from agent_runtime.config_loader import load_agent_config

from shared.logging.logger import get_logger

logger = get_logger(__name__)

def build_admin_database_url() -> str:
    """
    Build PostgreSQL admin connection URL.

    Required .env variables:
        POSTGRES_HOST
        POSTGRES_PORT
        POSTGRES_ADMIN_USER
        POSTGRES_ADMIN_PASSWORD
        POSTGRES_ADMIN_DB
    """
    load_dotenv()

    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")
    user = os.getenv("POSTGRES_ADMIN_USER")
    password = os.getenv("POSTGRES_ADMIN_PASSWORD")
    database = os.getenv("POSTGRES_ADMIN_DB", "postgres")

    missing = [
        name
        for name, value in {
            "POSTGRES_HOST": host,
            "POSTGRES_PORT": port,
            "POSTGRES_ADMIN_USER": user,
            "POSTGRES_ADMIN_PASSWORD": password,
        }.items()
        if not value
    ]

    if missing:
        raise RuntimeError(f"Missing required env variables: {', '.join(missing)}")

    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


def build_provider_database_url(
    host: str,
    port: str,
    db_name: str,
    db_user: str,
    db_password: str,
) -> str:
    """
    Build provider database connection URL.
    """
    return f"postgresql+psycopg://{db_user}:{db_password}@{host}:{port}/{db_name}"


def create_admin_engine() -> Engine:
    """
    Create SQLAlchemy engine for admin database connection.

    isolation_level='AUTOCOMMIT' is required because CREATE DATABASE
    cannot run inside a transaction block.
    """
    return create_engine(
        build_admin_database_url(),
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )


def database_exists(engine: Engine, db_name: str) -> bool:
    """
    Check whether PostgreSQL database exists.
    """
    query = text("SELECT 1 FROM pg_database WHERE datname = :db_name")

    with engine.connect() as conn:
        return conn.execute(query, {"db_name": db_name}).first() is not None


def role_exists(engine: Engine, role_name: str) -> bool:
    """
    Check whether PostgreSQL role/user exists.
    """
    query = text("SELECT 1 FROM pg_roles WHERE rolname = :role_name")

    with engine.connect() as conn:
        return conn.execute(query, {"role_name": role_name}).first() is not None


def quote_identifier(identifier: str) -> str:
    """
    Safely quote PostgreSQL identifier.

    This is used for database/user names because PostgreSQL does not allow
    binding identifiers as SQL parameters.
    """
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'

def escape_literal(value: str) -> str:
    """
    Escape string for SQL literal injection.

    Used only where PostgreSQL does not allow bind parameters.
    """
    return value.replace("'", "''")

def create_database_if_missing(engine: Engine, db_name: str) -> None:
    """
    Create PostgreSQL database if it does not exist.
    """
    if database_exists(engine, db_name):
        print(f"Database already exists: {db_name}")
        return

    with engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE {quote_identifier(db_name)}"))

    print(f"Database created: {db_name}")


def create_role_if_missing(engine: Engine, db_user: str, db_password: str) -> None:
    """
    Create PostgreSQL login role if it does not exist.

    If role already exists, update password.
    """
    quoted_user = quote_identifier(db_user)
    escaped_password = escape_literal(db_password)

    with engine.connect() as conn:
        if role_exists(engine, db_user):
            sql = (
                f"ALTER ROLE {quoted_user} "
                f"WITH LOGIN PASSWORD '{escaped_password}'"
            )
            conn.execute(text(sql))
            print(f"Role already exists; password updated: {db_user}")
            return

        sql = (
            f"CREATE ROLE {quoted_user} "
            f"WITH LOGIN PASSWORD '{escaped_password}'"
        )
        conn.execute(text(sql))

    print(f"Role created: {db_user}")




def grant_database_privileges(
    engine: Engine,
    db_name: str,
    db_user: str,
) -> None:
    """
    Grant provider database privileges to provider user.
    """
    quoted_db = quote_identifier(db_name)
    quoted_user = quote_identifier(db_user)

    with engine.connect() as conn:
        conn.execute(text(f"GRANT ALL PRIVILEGES ON DATABASE {quoted_db} TO {quoted_user}"))

    print(f"Database privileges granted: {db_user} -> {db_name}")


def grant_schema_privileges(
    db_name: str,
    db_user: str,
    db_password: str,
) -> None:
    """
    Grant schema-level privileges inside provider database.

    PostgreSQL database privileges alone are not enough.
    The user also needs privileges on the public schema.
    """
    load_dotenv()

    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")
    admin_user = os.getenv("POSTGRES_ADMIN_USER")
    admin_password = os.getenv("POSTGRES_ADMIN_PASSWORD")

    admin_provider_url = (
        f"postgresql+psycopg://{admin_user}:{admin_password}@{host}:{port}/{db_name}"
    )

    engine = create_engine(
        admin_provider_url,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )

    quoted_user = quote_identifier(db_user)

    with engine.connect() as conn:
        conn.execute(text(f"GRANT USAGE, CREATE ON SCHEMA public TO {quoted_user}"))
        conn.execute(text(f"ALTER SCHEMA public OWNER TO {quoted_user}"))

    print(f"Schema privileges granted on {db_name} to {db_user}")


def verify_provider_connection(
    db_name: str,
    db_user: str,
    db_password: str,
) -> None:
    """
    Verify provider database login works using provider credentials.
    """
    load_dotenv()

    host = os.getenv("POSTGRES_HOST")
    port = os.getenv("POSTGRES_PORT")

    provider_url = build_provider_database_url(
        host=host,
        port=port,
        db_name=db_name,
        db_user=db_user,
        db_password=db_password,
    )

    engine = create_engine(provider_url, pool_pre_ping=True)

    with engine.connect() as conn:
        row = conn.execute(text("SELECT current_database(), current_user")).fetchone()

    print("Provider DB connection verified")
    print(f"Database: {row[0]}")
    print(f"User: {row[1]}")


def bootstrap_provider_database(agent_config: dict) -> None:
    """
    Bootstrap database resources for one provider agent.

    Args:
        agent_config: Resolved agent configuration from config_loader.
    """
    db_config = agent_config["database"]

    db_name = db_config["db_name"]
    db_user = db_config["db_user"]
    db_password = db_config["db_password"]

    admin_engine = create_admin_engine()

    create_database_if_missing(admin_engine, db_name)
    create_role_if_missing(admin_engine, db_user, db_password)
    grant_database_privileges(admin_engine, db_name, db_user)
    grant_schema_privileges(db_name, db_user, db_password)
    verify_provider_connection(db_name, db_user, db_password)


if __name__ == "__main__":
    """
    Manual test:
        python -m agent_runtime.bootstrap --config agents/company_a/agent.yaml
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to provider agent.yaml")
    args = parser.parse_args()

    config = load_agent_config(args.config)
    bootstrap_provider_database(config)
