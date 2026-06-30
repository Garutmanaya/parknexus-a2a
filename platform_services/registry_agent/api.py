"""FastAPI router for ParkNexus A2A Registry Agent."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from platform_services.registry_agent import service
from platform_services.registry_agent.a2a_card import build_registry_agent_card
from platform_services.registry_agent.database import get_platform_db
from platform_services.registry_agent.schemas import (
    DiscoverAgentsRequest,
    DiscoverAgentsResponse,
    RegisterAgentRequest,
    RegisteredAgent,
)
from shared.logging.logger import get_logger
from shared.security.middleware import require_secure_a2a_request

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_platform_db)) -> dict:
    logger.debug("registry_health_requested")
    db.execute(text("SELECT 1"))
    return {"status": "healthy", "service": "registry_agent"}


@router.post("/agents/register", response_model=RegisteredAgent)
def register_agent(request: RegisterAgentRequest, db: Session = Depends(get_platform_db)):
    logger.info("registry_rest_register_received base_url=%s", request.agent_base_url)
    try:
        return service.register_agent(db, request.agent_base_url)
    except Exception as exc:
        logger.error("registry_rest_register_failed", exc_info=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/agents", response_model=list[RegisteredAgent])
def list_agents(db: Session = Depends(get_platform_db)):
    logger.info("registry_rest_list_agents_received")
    return service.list_agents(db)


@router.post("/agents/discover", response_model=DiscoverAgentsResponse)
def discover_agents(request: DiscoverAgentsRequest, db: Session = Depends(get_platform_db)):
    logger.info("registry_rest_discover_received skill_id=%s tag=%s streaming_required=%s", request.skill_id, request.tag, request.streaming_required)
    agents = service.discover_agents(db, request.skill_id, request.tag, request.streaming_required)
    return DiscoverAgentsResponse(count=len(agents), agents=agents)


@router.get("/.well-known/agent.json")
def get_agent_json() -> dict:
    return build_registry_agent_card()


@router.get("/.well-known/agent-card.json")
def get_agent_card_json() -> dict:
    return build_registry_agent_card()


def execute_registry_a2a(request: dict, db: Session) -> dict:
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})
    logger.info("registry_a2a_request_received method=%s request_id=%s", method, request_id)
    logger.debug("registry_a2a_params=%s", params)
    try:
        if method == "register_agent":
            agent = service.register_agent(db, params["agent_base_url"])
            return {"jsonrpc": "2.0", "id": request_id, "result": agent.model_dump(), "error": None}
        if method == "discover_agents":
            agents = service.discover_agents(db, params.get("skill_id"), params.get("tag"), params.get("streaming_required"))
            return {"jsonrpc": "2.0", "id": request_id, "result": {"count": len(agents), "agents": [agent.model_dump() for agent in agents]}, "error": None}
        if method == "list_agents":
            agents = service.list_agents(db)
            return {"jsonrpc": "2.0", "id": request_id, "result": {"count": len(agents), "agents": [agent.model_dump() for agent in agents]}, "error": None}
        return {"jsonrpc": "2.0", "id": request_id, "result": None, "error": {"code": -32601, "message": f"Unsupported registry method: {method}"}}
    except KeyError as exc:
        return {"jsonrpc": "2.0", "id": request_id, "result": None, "error": {"code": -32602, "message": f"Missing required parameter: {exc}"}}
    except Exception as exc:
        logger.error("registry_a2a_request_failed method=%s", method, exc_info=True)
        return {"jsonrpc": "2.0", "id": request_id, "result": None, "error": {"code": -32603, "message": str(exc)}}


@router.post("/a2a")
async def handle_a2a_request(request: dict, security_context: dict = Depends(require_secure_a2a_request), db: Session = Depends(get_platform_db)):
    return execute_registry_a2a(request, db)


@router.post("/a2a/stream")
async def handle_a2a_stream_request(request: dict, security_context: dict = Depends(require_secure_a2a_request), db: Session = Depends(get_platform_db)):
    async def event_generator():
        request_id = request.get("id")
        method = request.get("method")
        yield {"event": "task_started", "data": json.dumps({"request_id": request_id, "method": method, "agent": "registry_agent", "status": "started"})}
        await asyncio.sleep(0.05)
        result = execute_registry_a2a(request, db)
        yield {"event": "task_failed" if result.get("error") else "task_completed", "data": json.dumps(result, default=str)}
    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    print("Registry API router loaded")
