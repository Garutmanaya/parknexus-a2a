"""
Configuration loader for ParkNexus A2A provider agents.

This module loads:
- local environment variables from .env
- provider-specific YAML configuration from agents/<agent_id>/agent.yaml

No secrets should be hardcoded in YAML.
YAML references environment variable names for database credentials.
"""

import argparse
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from shared.logging.logger import get_logger

logger = get_logger(__name__)

def load_yaml_file(path: str | Path) -> dict[str, Any]:
    """
    Load YAML file as dictionary.

    Args:
        path: YAML file path.

    Returns:
        Parsed YAML dictionary.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If YAML is empty or invalid.
    """
    yaml_path = Path(path)

    if not yaml_path.exists():
        raise FileNotFoundError(f"YAML file not found: {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise ValueError(f"YAML file must contain a dictionary: {yaml_path}")

    return data


def required_env(name: str) -> str:
    """
    Read required environment variable.

    Args:
        name: Environment variable name.

    Returns:
        Environment variable value.

    Raises:
        RuntimeError: If variable is missing.
    """
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")

    return value


def load_agent_config(config_path: str | Path) -> dict[str, Any]:
    """
    Load provider agent configuration and resolve database credentials.

    Args:
        config_path: Path to agent.yaml.

    Returns:
        Agent config dictionary with resolved database values.
    """
    load_dotenv()

    config = load_yaml_file(config_path)

    database = config.get("database", {})

    db_name_env = database.get("db_name_env")
    db_user_env = database.get("db_user_env")
    db_password_env = database.get("db_password_env")

    if not db_name_env or not db_user_env or not db_password_env:
        raise RuntimeError(
            "database.db_name_env, database.db_user_env, and "
            "database.db_password_env are required in agent.yaml"
        )

    database["db_name"] = required_env(db_name_env)
    database["db_user"] = required_env(db_user_env)
    database["db_password"] = required_env(db_password_env)

    config["database"] = database
    config["postgres_host"] = required_env("POSTGRES_HOST")
    config["postgres_port"] = required_env("POSTGRES_PORT")

    return config


def load_a2a_config(a2a_path: str | Path) -> dict[str, Any]:
    """
    Load A2A-specific YAML configuration.

    Args:
        a2a_path: Path to a2a.yaml.

    Returns:
        Parsed A2A config dictionary.
    """
    return load_yaml_file(a2a_path)

def mask_secret(value: str) -> str:
    """
    Mask secret for safe console output.
    """
    if not value:
        return ""

    return "********"


if __name__ == "__main__":
    """
    Manual test:
        python -m agent_runtime.config_loader --config agents/company_a/agent.yaml
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to provider agent.yaml")
    args = parser.parse_args()

    agent_config = load_agent_config(args.config)
    db_config = agent_config["database"]

    print("Agent config loaded successfully")
    print(f"agent_id={agent_config['agent_id']}")
    print(f"display_name={agent_config['display_name']}")
    print(f"server_port={agent_config['server']['port']}")
    print(f"db_name={db_config['db_name']}")
    print(f"db_user={db_config['db_user']}")
    print(f"db_password={mask_secret(db_config['db_password'])}")
