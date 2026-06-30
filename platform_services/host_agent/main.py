"""
FastAPI entrypoint for ParkNexus A2A Host Agent.

Run:
    uvicorn platform_services.host_agent.main:app --reload --port 8030
"""

from fastapi import FastAPI

from platform_services.host_agent.api import router

from shared.logging.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="ParkNexus A2A Host Agent",
    version="0.1.0",
    description="User-facing Host Agent for multi-provider parking discovery.",
)

app.include_router(router)


@app.get("/")
def root() -> dict:
    """
    Root endpoint.
    """
    return {
        "service": "host_agent",
        "status": "running",
        "docs": "/docs",
    }


if __name__ == "__main__":
    print("Host Agent app loaded successfully")
