"""
FastAPI entrypoint for ParkNexus A2A Host Agent.

Run:
    uvicorn platform_services.host_agent.main:app --reload --port 8030
"""

from fastapi import FastAPI

from platform_services.host_agent.api import router

from shared.logging.logger import get_logger
from fastapi.middleware.cors import CORSMiddleware

logger = get_logger(__name__)

app = FastAPI(
    title="ParkNexus A2A Host Agent",
    version="0.1.0",
    description="User-facing Host Agent for multi-provider parking discovery.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
