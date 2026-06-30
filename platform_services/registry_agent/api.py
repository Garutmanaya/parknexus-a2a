"""
FastAPI router for ParkNexus A2A Registry Agent.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from platform_services.registry_agent.database import get_platform_db
from platform_services.registry_agent.schemas import (
    DiscoverAgentsRequest,
    DiscoverAgentsResponse,
    RegisterAgentRequest,
    RegisteredAgent,
)
from platform_services.registry_agent import service
from sqlalchemy import text

import asyncio
import json

from sse_starlette.sse import EventSourceResponse

from shared.security.middleware import require_secure_a2a_request
from platform_services.registry_agent.a2a_card import build_registry_agent_card

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_platform_db)) -> dict:
    """
    Registry health check.
    """
    
    db.execute(text("SELECT 1"))

    return {
        "status": "healthy",
        "service": "registry_agent",
    }


@router.post("/agents/register", response_model=RegisteredAgent)
def register_agent(
    request: RegisterAgentRequest,
    db: Session = Depends(get_platform_db),
):
    """
    Register a provider agent using its base URL.
    """
    try:
        return service.register_agent(db, request.agent_base_url)

    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/agents", response_model=list[RegisteredAgent])
def list_agents(db: Session = Depends(get_platform_db)):
    """
    List registered provider agents.
    """
    return service.list_agents(db)


@router.post("/agents/discover", response_model=DiscoverAgentsResponse)
def discover_agents(
    request: DiscoverAgentsRequest,
    db: Session = Depends(get_platform_db),
):
    """
    Discover agents by skill/capability.
    """
    agents = service.discover_agents(
        db=db,
        skill_id=request.skill_id,
        tag=request.tag,
        streaming_required=request.streaming_required,
    )

    return DiscoverAgentsResponse(
        count=len(agents),
        agents=agents,
    )

@router.get("/.well-known/agent.json")
def get_agent_json() -> dict:
    """
    Return Registry Agent Card.
    """
    return build_registry_agent_card()


@router.get("/.well-known/agent-card.json")
def get_agent_card_json() -> dict:
    """
    Return Registry Agent Card.
    """
    return build_registry_agent_card()


@router.post("/a2a")
async def handle_a2a_request(
    request: dict,
    security_context: dict = Depends(require_secure_a2a_request),
    db: Session = Depends(get_platform_db),
):
    """
    Secure A2A JSON-RPC endpoint for Registry Agent.

    Supported methods:
        - register_agent
        - discover_agents
        - list_agents
    """
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params", {})

    try:
        if method == "register_agent":
            agent = service.register_agent(
                db=db,
                agent_base_url=params["agent_base_url"],
            )

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": agent.model_dump(),
                "error": None,
            }

        if method == "discover_agents":
            agents = service.discover_agents(
                db=db,
                skill_id=params.get("skill_id"),
                tag=params.get("tag"),
                streaming_required=params.get("streaming_required"),
            )

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "count": len(agents),
                    "agents": [agent.model_dump() for agent in agents],
                },
                "error": None,
            }

        if method == "list_agents":
            agents = service.list_agents(db)

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "count": len(agents),
                    "agents": [agent.model_dump() for agent in agents],
                },
                "error": None,
            }

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": None,
            "error": {
                "code": -32601,
                "message": f"Unsupported registry method: {method}",
            },
        }

    except KeyError as exc:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": None,
            "error": {
                "code": -32602,
                "message": f"Missing required parameter: {exc}",
            },
        }

    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": None,
            "error": {
                "code": -32603,
                "message": str(exc),
            },
        }


@router.post("/a2a/stream")
async def handle_a2a_stream_request(
    request: dict,
    security_context: dict = Depends(require_secure_a2a_request),
    db: Session = Depends(get_platform_db),
):
    """
    Secure A2A SSE endpoint for Registry Agent.
    """

    async def event_generator():
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        def sse(event_name: str, payload: dict) -> dict:
            return {
                "event": event_name,
                "data": json.dumps(payload),
            }

        yield sse(
            "task_started",
            {
                "request_id": request_id,
                "method": method,
                "agent": "registry_agent",
                "status": "started",
            },
        )

        await asyncio.sleep(0.05)

        try:
            yield sse(
                "task_progress",
                {
                    "request_id": request_id,
                    "method": method,
                    "status": "processing",
                },
            )

            if method == "register_agent":
                agent = service.register_agent(
                    db=db,
                    agent_base_url=params["agent_base_url"],
                )

                yield sse(
                    "task_completed",
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": agent.model_dump(),
                        "error": None,
                    },
                )
                return

            if method == "discover_agents":
                agents = service.discover_agents(
                    db=db,
                    skill_id=params.get("skill_id"),
                    tag=params.get("tag"),
                    streaming_required=params.get("streaming_required"),
                )

                yield sse(
                    "task_completed",
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "count": len(agents),
                            "agents": [agent.model_dump() for agent in agents],
                        },
                        "error": None,
                    },
                )
                return

            if method == "list_agents":
                agents = service.list_agents(db)

                yield sse(
                    "task_completed",
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "count": len(agents),
                            "agents": [agent.model_dump() for agent in agents],
                        },
                        "error": None,
                    },
                )
                return

            yield sse(
                "task_failed",
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": None,
                    "error": {
                        "code": -32601,
                        "message": f"Unsupported registry method: {method}",
                    },
                },
            )

        except Exception as exc:
            yield sse(
                "task_failed",
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": None,
                    "error": {
                        "code": -32603,
                        "message": str(exc),
                    },
                },
            )

    return EventSourceResponse(event_generator())



if __name__ == "__main__":
    """
    Manual router inspection:
        python -m platform_services.registry_agent.api
    """
    print("Registry API router loaded")
    for route in router.routes:
        print(f"{','.join(route.methods)} {route.path}")