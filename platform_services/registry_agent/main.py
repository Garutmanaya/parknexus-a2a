"""
FastAPI entrypoint for ParkNexus A2A Registry Agent.

Run:
    uvicorn platform_services.registry_agent.main:app --reload --port 8020
"""

from fastapi import FastAPI

from platform_services.registry_agent.api import router
from platform_services.registry_agent.database import (
    bootstrap_platform_database,
    create_platform_tables,
)


# Local-friendly startup.
# Later, for cloud, split bootstrap into a one-time platform setup job.
bootstrap_platform_database()
create_platform_tables()


app = FastAPI(
    title="ParkNexus A2A Registry Agent",
    version="0.1.0",
    description="Registry for discovering ParkNexus provider Agent Cards.",
)

app.include_router(router)


@app.get("/")
def root() -> dict:
    """
    Root endpoint.
    """
    return {
        "service": "registry_agent",
        "status": "running",
        "docs": "/docs",
    }


if __name__ == "__main__":
    """
    Manual test:
        python -m platform_services.registry_agent.main
    """
    print("Registry Agent app loaded successfully")
    print("Run: uvicorn platform_services.registry_agent.main:app --reload --port 8020")