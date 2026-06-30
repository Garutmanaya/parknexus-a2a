"""
LangGraph workflow for ParkNexus Host Agent.

Flow:
    user message
      -> parse intent
      -> discover provider agents
      -> call providers through secure A2A
      -> rank results
      -> build response

Provider agents never receive raw natural language.
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from platform_services.host_agent.intent import ParkingIntent, parse_user_request
from platform_services.host_agent.service import call_provider_search, discover_search_agents
from platform_services.host_agent.schemas import ProviderSlotResult

from shared.logging.logger import get_logger

logger = get_logger(__name__)

class HostAgentState(TypedDict, total=False):
    """
    Host Agent graph state.
    """

    user_message: str
    intent: ParkingIntent
    providers: list[dict]
    slots: list[ProviderSlotResult]
    response: dict


def parse_intent_node(state: HostAgentState) -> HostAgentState:
    """
    Convert user natural language into structured intent.
    """
    intent = parse_user_request(state["user_message"])
    state["intent"] = intent
    return state


def should_continue_after_intent(state: HostAgentState) -> str:
    """
    Stop if clarification is required.
    """
    intent = state["intent"]

    if intent.intent == "clarify":
        return "clarify"

    return "discover"


def clarification_node(state: HostAgentState) -> HostAgentState:
    """
    Return clarification response.
    """
    intent = state["intent"]

    state["response"] = {
        "type": "clarification",
        "intent": intent.model_dump(),
        "message": intent.clarification_question,
        "count": 0,
        "slots": [],
    }

    return state


def discover_providers_node(state: HostAgentState) -> HostAgentState:
    """
    Discover provider agents from Registry via secure A2A.
    """
    state["providers"] = discover_search_agents()
    return state


def call_providers_node(state: HostAgentState) -> HostAgentState:
    """
    Call discovered providers through secure A2A.
    """
    intent = state["intent"]
    all_slots: list[ProviderSlotResult] = []

    max_price_per_hour = None
    #if intent.budget_amount is not None and str(intent.budget_unit) == "BudgetUnit.HOUR":
    if intent.budget_amount is not None and intent.budget_unit.value == "hour":
        max_price_per_hour = intent.budget_amount

    for provider in state.get("providers", []):
        provider_slots = call_provider_search(
            provider=provider,
            request_id=f"host-search-{provider['name']}",
            level_name=intent.level_name,
            ev_charger=intent.ev_charger,
            handicap=intent.handicap,
            budget_amount=intent.budget_amount,
            budget_unit=intent.budget_unit.value if intent.budget_unit else None,
            duration_minutes=intent.duration_minutes,
            limit=5,
        )
        all_slots.extend(provider_slots)

    state["slots"] = all_slots
    return state


def rank_slots_node(state: HostAgentState) -> HostAgentState:
    """
    Rank results based on intent sort preference.
    """
    intent = state["intent"]
    slots = state.get("slots", [])

    if intent.sort_by and intent.sort_by[0] == "distance":
        sorted_slots = sorted(
            slots,
            key=lambda slot: (
                slot.distance_to_entrance_meters,
                slot.price_per_hour,
            ),
        )
    else:
        sorted_slots = sorted(
            slots,
            key=lambda slot: (
                slot.price_per_hour,
                slot.distance_to_entrance_meters,
            ),
        )

    state["slots"] = sorted_slots
    return state


def build_response_node(state: HostAgentState) -> HostAgentState:
    """
    Build final Host Agent response.
    """
    intent = state["intent"]
    slots = state.get("slots", [])

    state["response"] = {
        "type": "parking_results",
        "intent": intent.model_dump(),
        "count": len(slots),
        "slots": [slot.model_dump() for slot in slots],
    }

    return state


def build_host_graph():
    """
    Build compiled LangGraph Host Agent workflow.
    """
    graph = StateGraph(HostAgentState)

    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("clarification", clarification_node)
    graph.add_node("discover_providers", discover_providers_node)
    graph.add_node("call_providers", call_providers_node)
    graph.add_node("rank_slots", rank_slots_node)
    graph.add_node("build_response", build_response_node)

    graph.set_entry_point("parse_intent")

    graph.add_conditional_edges(
        "parse_intent",
        should_continue_after_intent,
        {
            "clarify": "clarification",
            "discover": "discover_providers",
        },
    )

    graph.add_edge("clarification", END)
    graph.add_edge("discover_providers", "call_providers")
    graph.add_edge("call_providers", "rank_slots")
    graph.add_edge("rank_slots", "build_response")
    graph.add_edge("build_response", END)

    return graph.compile()


host_graph = build_host_graph()


def run_host_agent(user_message: str) -> dict:
    """
    Run Host Agent graph.
    """
    result = host_graph.invoke({"user_message": user_message})
    return result["response"]


if __name__ == "__main__":
    """
    Manual test:
        python -m platform_services.host_agent.graph
    """
    response = run_host_agent("Find me a cheap EV parking slot under $15 per hour")
    print(response)
