"""
A2A Agent Card generator for ParkNexus Registry Agent.
"""

import os
from dotenv import load_dotenv


def required_env(name: str) -> str:
    load_dotenv()
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_registry_agent_card() -> dict:
    """
    Build Registry Agent Card.

    No secrets are exposed in this card.
    """
    base_url = required_env("REGISTRY_AGENT_BASE_URL").rstrip("/")

    return {
        "name": required_env("REGISTRY_AGENT_NAME"),
        "description": "ParkNexus A2A Registry Agent for provider discovery.",
        "version": required_env("REGISTRY_AGENT_VERSION"),
        "url": base_url,
        "provider": {
            "organization": "ParkNexus A2A",
            "url": base_url,
        },
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
            },
            "hmacSignature": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Signature",
                "description": "HMAC-SHA256 signature over agent_id, request_id, timestamp, and body.",
            },
        },
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": "register_agent",
                "name": "Register Agent",
                "description": "Register a provider agent by reading its Agent Card.",
                "tags": ["registry", "discovery", "registration"],
            },
            {
                "id": "discover_agents",
                "name": "Discover Agents",
                "description": "Discover registered provider agents by skill, tag, and capability.",
                "tags": ["registry", "discovery"],
            },
            {
                "id": "list_agents",
                "name": "List Agents",
                "description": "List all active registered provider agents.",
                "tags": ["registry", "metadata"],
            },
        ],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(build_registry_agent_card(), indent=2))
