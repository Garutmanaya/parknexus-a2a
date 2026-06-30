"""Service layer for ParkNexus A2A Registry Agent."""

import httpx
from sqlalchemy.orm import Session

from platform_services.registry_agent.models import RegisteredAgentModel, utc_now
from platform_services.registry_agent.schemas import RegisteredAgent
from shared.config.runtime import get_httpx_verify_tls
from shared.logging.logger import get_logger

logger = get_logger(__name__)

AGENT_CARD_PATHS = ["/.well-known/agent-card.json", "/.well-known/agent.json"]


def normalize_base_url(agent_base_url: str) -> str:
    return agent_base_url.rstrip("/")


def fetch_agent_card(agent_base_url: str) -> dict:
    base_url = normalize_base_url(agent_base_url)
    last_error = None
    logger.info("agent_card_fetch_started base_url=%s", base_url)
    for path in AGENT_CARD_PATHS:
        url = f"{base_url}{path}"
        try:
            logger.debug("agent_card_fetch_attempt url=%s", url)
            response = httpx.get(url, timeout=5.0, verify=get_httpx_verify_tls())
            if response.status_code == 200:
                logger.info("agent_card_fetch_completed url=%s", url)
                return response.json()
            last_error = f"{url} returned HTTP {response.status_code}"
        except Exception as exc:
            last_error = str(exc)
            logger.warning("agent_card_fetch_attempt_failed url=%s error=%s", url, exc)
    logger.error("agent_card_fetch_failed base_url=%s error=%s", base_url, last_error)
    raise RuntimeError(f"Could not fetch Agent Card from {agent_base_url}: {last_error}")


def validate_agent_card(card: dict) -> None:
    required_fields = ["name", "url", "skills", "capabilities"]
    missing = [field for field in required_fields if field not in card]
    if missing:
        raise ValueError(f"Agent Card missing fields: {', '.join(missing)}")
    if not isinstance(card["skills"], list):
        raise ValueError("Agent Card skills must be a list")
    if not isinstance(card["capabilities"], dict):
        raise ValueError("Agent Card capabilities must be a dictionary")


def to_schema(model: RegisteredAgentModel) -> RegisteredAgent:
    return RegisteredAgent(name=model.name, description=model.description, version=model.version, url=model.url, provider=model.provider, capabilities=model.capabilities, skills=model.skills)


def register_agent(db: Session, agent_base_url: str) -> RegisteredAgent:
    logger.info("agent_register_started base_url=%s", agent_base_url)
    card = fetch_agent_card(agent_base_url)
    validate_agent_card(card)
    existing = db.query(RegisteredAgentModel).filter(RegisteredAgentModel.name == card["name"]).first()
    if existing:
        existing.description = card.get("description")
        existing.version = card.get("version")
        existing.url = card["url"]
        existing.provider = card.get("provider", {})
        existing.capabilities = card.get("capabilities", {})
        existing.skills = card.get("skills", [])
        existing.is_active = True
        existing.updated_at = utc_now()
        db.commit(); db.refresh(existing)
        logger.info("agent_register_updated name=%s url=%s", existing.name, existing.url)
        return to_schema(existing)
    model = RegisteredAgentModel(name=card["name"], description=card.get("description"), version=card.get("version"), url=card["url"], provider=card.get("provider", {}), capabilities=card.get("capabilities", {}), skills=card.get("skills", []), is_active=True)
    db.add(model); db.commit(); db.refresh(model)
    logger.info("agent_register_created name=%s url=%s", model.name, model.url)
    return to_schema(model)


def list_agents(db: Session) -> list[RegisteredAgent]:
    models = db.query(RegisteredAgentModel).filter(RegisteredAgentModel.is_active.is_(True)).order_by(RegisteredAgentModel.name).all()
    logger.info("agent_list_completed count=%s", len(models))
    return [to_schema(model) for model in models]


def discover_agents(db: Session, skill_id: str | None = None, tag: str | None = None, streaming_required: bool | None = None) -> list[RegisteredAgent]:
    logger.info("agent_discover_started skill_id=%s tag=%s streaming_required=%s", skill_id, tag, streaming_required)
    agents = list_agents(db)
    results = []
    for agent in agents:
        if streaming_required is not None and bool(agent.capabilities.get("streaming", False)) != streaming_required:
            continue
        if skill_id and not any(skill.get("id") == skill_id for skill in agent.skills):
            continue
        if tag and not any(tag in skill.get("tags", []) for skill in agent.skills):
            continue
        results.append(agent)
    logger.info("agent_discover_completed count=%s", len(results))
    return results
