"""
Common environment utilities.
"""

import os
from dotenv import load_dotenv


def required_env(name: str) -> str:
    """
    Read required env variable.
    """
    load_dotenv()

    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")

    return value


def optional_env(name: str, default=None):
    """
    Read optional env variable.
    """
    load_dotenv()
    return os.getenv(name, default)


def bool_env(name: str, default: bool = False) -> bool:
    """
    Read boolean env variable.
    """
    load_dotenv()
    value = os.getenv(name)

    if value is None:
        return default

    return value.lower() in ("true", "1", "yes", "y")


def int_env(name: str, default: int) -> int:
    """
    Read integer env variable.
    """
    load_dotenv()
    value = os.getenv(name)

    if value is None:
        return default

    return int(value)
