"""
A2A Agent Card generator for ParkNexus A2A provider agents.

This module generates Agent Card JSON from:
- agent.yaml
- a2a.yaml

The generated card is exposed by the provider API at:
- /.well-known/agent.json
- /.well-known/agent-card.json

No secrets or internal database information should appear in the Agent Card.
"""

import argparse
import json
from typing import Any

from agent_runtime.config_loader import load_a2a_config, load_agent_config

from shared.logging.logger import get_logger

logger = get_logger(__name__)

def build_skill(skill_config: dict[str, Any]) -> dict[str, Any]:
    """
    Build one A2A skill entry from a2a.yaml.
    """
    skill = {
        "id": skill_config["id"],
        "name": skill_config["name"],
        "description": skill_config.get("description", ""),
        "tags": skill_config.get("tags", []),
    }

    # Provider-specific schema contracts are advertised in the Agent Card.
    # Host Agent uses these schemas to validate/marshal provider-specific payloads
    # before sending A2A requests.
    if "input_schema" in skill_config:
        skill["input_schema"] = skill_config["input_schema"]
    if "output_schema" in skill_config:
        skill["output_schema"] = skill_config["output_schema"]

    return skill


def build_agent_card(
    agent_config: dict[str, Any],
    a2a_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Build A2A Agent Card JSON.

    Args:
        agent_config: Resolved provider config from agent.yaml.
        a2a_config: A2A metadata from a2a.yaml.

    Returns:
        Agent Card dictionary.
    """
    server = agent_config["server"]
    agent_card = a2a_config["agent_card"]

    public_base_url = server["public_base_url"].rstrip("/")

    return {
        "name": agent_card["name"],
        "description": agent_card.get("description", agent_config.get("description", "")),
        "version": str(agent_card.get("version", "1.0.0")),
        "url": public_base_url,
        "provider": {
            "organization": a2a_config.get("provider", {}).get(
                "organization",
                agent_config["display_name"],
            ),
            "url": a2a_config.get("provider", {}).get("url", public_base_url),
        },
        "capabilities": {
            "streaming": bool(a2a_config.get("capabilities", {}).get("streaming", False)),
            "pushNotifications": bool(
                a2a_config.get("capabilities", {}).get("push_notifications", False)
            ),
            "stateTransitionHistory": bool(
                a2a_config.get("capabilities", {}).get(
                    "state_transition_history",
                    False,
                )
            ),
        },
        "defaultInputModes": a2a_config.get("default_input_modes", ["application/json"]),
        "defaultOutputModes": a2a_config.get("default_output_modes", ["application/json"]),
        "skills": [
            build_skill(skill)
            for skill in a2a_config.get("skills", [])
        ],
    }


if __name__ == "__main__":
    """
    Manual test:
        python -m agent_runtime.a2a_card \
          --config agents/company_a/agent.yaml \
          --a2a agents/company_a/a2a.yaml
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to agent.yaml")
    parser.add_argument("--a2a", required=True, help="Path to a2a.yaml")
    args = parser.parse_args()

    agent_config = load_agent_config(args.config)
    a2a_config = load_a2a_config(args.a2a)

    card = build_agent_card(agent_config, a2a_config)

    print(json.dumps(card, indent=2))
