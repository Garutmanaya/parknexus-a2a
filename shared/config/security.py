"""
Security configuration.
"""

from shared.config.env import int_env, required_env


def get_a2a_shared_secret() -> str:
    return required_env("A2A_SHARED_SECRET")


def get_allowed_agent_tokens() -> dict[str, str]:
    return {
        required_env("HOST_AGENT_ID"): required_env("HOST_AGENT_TOKEN"),
        required_env("REGISTRY_AGENT_ID"): required_env("REGISTRY_AGENT_TOKEN"),
    }


def get_provider_token() -> str:
    return required_env("PROVIDER_AGENT_TOKEN")


def get_max_clock_skew_seconds() -> int:
    return int_env("A2A_MAX_CLOCK_SKEW_SECONDS", 300)
