"""
Logging configuration.
"""

from shared.config.env import optional_env


def get_log_dir() -> str:
    return optional_env("LOG_DIR", "./logs")


def get_log_level() -> str:
    return optional_env("LOG_LEVEL", "INFO").upper()
