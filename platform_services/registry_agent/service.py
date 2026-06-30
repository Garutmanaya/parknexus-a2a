"""
Service layer for ParkNexus A2A Registry Agent.

The registry discovers provider agents by reading their Agent Cards and stores
them in the platform database.

Important:
    Registry does not access provider-owned parking databases.
"""

import httpx
from sqlalchemy.orm import Session

from platform_services.registry_agent.models import RegisteredAgentModel
from platform_services.registry_agent.schemas import RegisteredAgent
from shared.config.runtime import get_httpx_verify_tls
from platform_services.registry_agent.models import RegisteredAgentModel, utc_now

AGENT_CARD_PATHS = [
    "/.well-known/agent-card.json",
    "/.well-known/agent.json",
]


def normalize_base_url(agent_base_url: str) -> str:
    """
    Normalize base URL by removing trailing slash.
    """
    return agent_base_url.rstrip("/")


def fetch_agent_card(agent_base_url: str) -> dict:
    """
    Fetch Agent Card from provider.
    """
    base_url = normalize_base_url(agent_base_url)
    last_error = None

    for path in AGENT_CARD_PATHS:
        url = f"{base_url}{path}"

        try:
            response = httpx.get(
                url,
                timeout=5.0,
                verify=get_httpx_verify_tls(),
            )

            if response.status_code == 200:
                return response.json()

            last_error = f"{url} returned HTTP {response.status_code}"

        except Exception as exc:
            last_error = str(exc)

    raise RuntimeError(f"Could not fetch Agent Card from {agent_base_url}: {last_error}")


def validate_agent_card(card: dict) -> None:
    """
    Validate minimum Agent Card fields required by ParkNexus registry.
    """
    required_fields = ["name", "url", "skills", "capabilities"]
    missing = [field for field in required_fields if field not in card]

    if missing:
        raise ValueError(f"Agent Card missing fields: {', '.join(missing)}")

    if not isinstance(card["skills"], list):
        raise ValueError("Agent Card skills must be a list")

    if not isinstance(card["capabilities"], dict):
        raise ValueError("Agent Card capabilities must be a dictionary")


def to_schema(model: RegisteredAgentModel) -> RegisteredAgent:
    """
    Convert ORM model to API schema.
    """
    return RegisteredAgent(
        name=model.name,
        description=model.description,
        version=model.version,
        url=model.url,
        provider=model.provider,
        capabilities=model.capabilities,
        skills=model.skills,
    )


def register_agent(db: Session, agent_base_url: str) -> RegisteredAgent:
    """
    Register or update provider agent by fetching its Agent Card.
    """
    card = fetch_agent_card(agent_base_url)
    validate_agent_card(card)

    existing = (
        db.query(RegisteredAgentModel)
        .filter(RegisteredAgentModel.name == card["name"])
        .first()
    )

    if existing:
        existing.description = card.get("description")
        existing.version = card.get("version")
        existing.url = card["url"]
        existing.provider = card.get("provider", {})
        existing.capabilities = card.get("capabilities", {})
        existing.skills = card.get("skills", [])
        existing.is_active = True
        existing.updated_at = utc_now()
        #existing.updated_at = RegisteredAgentModel.updated_at.default.arg()

        db.commit()
        db.refresh(existing)

        return to_schema(existing)

    model = RegisteredAgentModel(
        name=card["name"],
        description=card.get("description"),
        version=card.get("version"),
        url=card["url"],
        provider=card.get("provider", {}),
        capabilities=card.get("capabilities", {}),
        skills=card.get("skills", []),
        is_active=True,
    )

    db.add(model)
    db.commit()
    db.refresh(model)

    return to_schema(model)


def list_agents(db: Session) -> list[RegisteredAgent]:
    """
    Return active registered agents.
    """
    models = (
        db.query(RegisteredAgentModel)
        .filter(RegisteredAgentModel.is_active.is_(True))
        .order_by(RegisteredAgentModel.name)
        .all()
    )

    return [to_schema(model) for model in models]


def discover_agents(
    db: Session,
    skill_id: str | None = None,
    tag: str | None = None,
    streaming_required: bool | None = None,
) -> list[RegisteredAgent]:
    """
    Discover registered agents by skill and capability filters.
    """
    agents = list_agents(db)
    results = []

    for agent in agents:
        if streaming_required is not None:
            streaming = bool(agent.capabilities.get("streaming", False))
            if streaming != streaming_required:
                continue

        if skill_id:
            skill_match = any(skill.get("id") == skill_id for skill in agent.skills)
            if not skill_match:
                continue

        if tag:
            tag_match = any(tag in skill.get("tags", []) for skill in agent.skills)
            if not tag_match:
                continue

        results.append(agent)

    return results


if __name__ == "__main__":
    """
    Manual test:
        python -m platform_services.registry_agent.service
    """
    print("Persistent registry service loaded successfully")