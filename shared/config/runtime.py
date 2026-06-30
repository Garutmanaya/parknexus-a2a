"""
Runtime configuration shared across services.
"""

from shared.config.env import bool_env, required_env


def get_registry_agent_base_url() -> str:
    return required_env("REGISTRY_AGENT_BASE_URL").rstrip("/")


def get_host_agent_base_url() -> str:
    return required_env("HOST_AGENT_BASE_URL").rstrip("/")


def get_httpx_verify_tls() -> bool:
    """
    Local self-signed cert:
        False

    Cloud:
        True
    """
    return bool_env("LOCAL_TLS_VERIFY", False)
