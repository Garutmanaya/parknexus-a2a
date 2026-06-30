"""
FastAPI application factory for config-driven ParkNexus A2A provider agents.

This module supports dynamic provider startup.

Examples:
    uvicorn "agent_runtime.main:create_app_from_config('agents/company_a/agent.yaml')" --factory --port 8011

Recommended local runner:
    python -m agent_runtime.run --config agents/company_a/agent.yaml --port 8011
"""

import agent_runtime.models  # noqa: F401
from fastapi import FastAPI

from agent_runtime.api import create_provider_router
from agent_runtime.config_loader import load_agent_config
from agent_runtime.database import create_provider_engine, create_session_factory, create_tables
from agent_runtime.seed import seed_provider_database
from agent_runtime.config_loader import load_a2a_config, load_agent_config

from shared.logging.logger import get_logger

logger = get_logger(__name__)

def create_app(agent_config: dict, a2a_config: dict) -> FastAPI:
#def create_app(agent_config: dict) -> FastAPI:
    """
    Create FastAPI app from resolved provider config.
    """
    seed_provider_database(agent_config)

    engine = create_provider_engine(agent_config)
    create_tables(engine)

    session_factory = create_session_factory(engine)

    app = FastAPI(
        title=f"ParkNexus A2A - {agent_config['display_name']}",
        version="0.1.0",
        description=agent_config.get("description", "ParkNexus provider agent."),
    )

    #app.include_router(create_provider_router(agent_config, session_factory))
    app.include_router(create_provider_router(agent_config, a2a_config, session_factory))

    @app.get("/")
    def root() -> dict:
        """
        Root endpoint for provider agent.
        """
        return {
            "service": "provider_agent",
            "agent_id": agent_config["agent_id"],
            "display_name": agent_config["display_name"],
            "status": "running",
            "docs": "/docs",
        }

    return app


def create_app_from_config(config_path: str, a2a_path: str) -> FastAPI:
    """
    Create FastAPI app from agent.yaml and a2a.yaml paths.
    """
    agent_config = load_agent_config(config_path)
    a2a_config = load_a2a_config(a2a_path)
    return create_app(agent_config, a2a_config) 




# Default app kept only for basic import compatibility.
#app = create_app_from_config("agents/company_a/agent.yaml")

"""
No default app is created here.

Use:
    python -m agent_runtime.run --config agents/company_a/agent.yaml --port 8011
"""
app = None

if __name__ == "__main__":
    """
    Manual test:
        python -m agent_runtime.main
    """
    print("Use agent_runtime.run for CLI startup:")
    print("python -m agent_runtime.run --config agents/company_a/agent.yaml --port 8011")
