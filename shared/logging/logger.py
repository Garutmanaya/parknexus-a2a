"""
Common logger factory for ParkNexus.
"""

import logging
import os
from pathlib import Path


from shared.logging.config import get_log_dir, get_log_level


_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(message)s"
)


def get_logger(module_name: str) -> logging.Logger:
    """
    Create logger.

    File name defaults to module name.
    Example:
        host_agent.log
        registry_agent.log
        provider_agent.log
    """
    logger = logging.getLogger(module_name)

    if logger.handlers:
        return logger

    logger.setLevel(get_log_level())
    logger.propagate = False

    formatter = logging.Formatter(_FORMAT)

    log_dir = Path(get_log_dir())
    log_dir.mkdir(parents=True, exist_ok=True)

    safe_name = module_name.replace(".", "_")
    file_path = log_dir / f"{safe_name}.log"

    file_handler = logging.FileHandler(file_path)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
