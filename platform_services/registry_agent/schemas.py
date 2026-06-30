"""
Pydantic schemas for ParkNexus A2A Registry Agent.
"""

from pydantic import BaseModel


class RegisterAgentRequest(BaseModel):
    """
    Register a provider agent by base URL.
    """

    agent_base_url: str


class RegisteredAgent(BaseModel):
    """
    Registered provider agent metadata.
    """

    name: str
    description: str | None = None
    version: str | None = None
    url: str
    provider: dict = {}
    capabilities: dict = {}
    skills: list[dict] = []


class DiscoverAgentsRequest(BaseModel):
    """
    Discover agents by skill/capability filters.
    """

    skill_id: str | None = None
    tag: str | None = None
    streaming_required: bool | None = None


class DiscoverAgentsResponse(BaseModel):
    """
    Discovery response.
    """

    count: int
    agents: list[RegisteredAgent]


if __name__ == "__main__":
    print("Registry schemas loaded successfully")
