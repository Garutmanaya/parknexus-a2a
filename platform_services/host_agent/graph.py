"""LangGraph workflow for ParkNexus Host Agent."""

from typing import TypedDict
from decimal import Decimal

from langgraph.graph import END, StateGraph

from platform_services.host_agent.intent import ParkingIntent, parse_user_request
from platform_services.host_agent.service import call_provider_search, discover_search_agents
from platform_services.host_agent.schemas import ProviderSlotResult
from shared.logging.logger import get_logger

logger = get_logger(__name__)


class HostAgentState(TypedDict, total=False):
    user_message: str
    intent: ParkingIntent
    providers: list[dict]
    slots: list[ProviderSlotResult]
    response: dict


def parse_intent_node(state: HostAgentState) -> HostAgentState:
    logger.info("graph_node_started node=parse_intent")
    state["intent"] = parse_user_request(state["user_message"])
    return state


def should_continue_after_intent(state: HostAgentState) -> str:
    return "clarify" if state["intent"].intent == "clarify" else "discover"


def clarification_node(state: HostAgentState) -> HostAgentState:
    logger.info("graph_node_started node=clarification")
    intent = state["intent"]
    state["response"] = {"type": "clarification", "intent": intent.model_dump(), "message": intent.clarification_question, "count": 0, "slots": []}
    return state


def discover_providers_node(state: HostAgentState) -> HostAgentState:
    logger.info("graph_node_started node=discover_providers")
    state["providers"] = discover_search_agents()
    return state


def call_providers_node(state: HostAgentState) -> HostAgentState:
    logger.info("graph_node_started node=call_providers")
    intent = state["intent"]
    all_slots: list[ProviderSlotResult] = []
    for provider in state.get("providers", []):
        all_slots.extend(call_provider_search(
            provider=provider,
            request_id=f"host-search-{provider['name']}",
            level_name=intent.level_name,
            ev_charger=intent.ev_charger,
            handicap=intent.handicap,
            budget_amount=intent.budget_amount,
            budget_unit=intent.budget_unit.value if intent.budget_unit else None,
            duration_minutes=intent.duration_minutes,
            limit=5,
        ))
    state["slots"] = all_slots
    return state


def rank_slots_node(state: HostAgentState) -> HostAgentState:
    logger.info("graph_node_started node=rank_slots")
    intent = state["intent"]
    slots = state.get("slots", [])
    high = Decimal("999999999")
    if intent.sort_by and intent.sort_by[0] == "distance":
        slots = sorted(slots, key=lambda slot: (slot.distance_to_entrance_meters, slot.estimated_price or slot.hourly_rate or high))
    else:
        slots = sorted(slots, key=lambda slot: (slot.estimated_price or slot.hourly_rate or high, slot.distance_to_entrance_meters))
    state["slots"] = slots
    return state


def build_response_node(state: HostAgentState) -> HostAgentState:
    logger.info("graph_node_started node=build_response")
    intent = state["intent"]
    slots = state.get("slots", [])
    state["response"] = {"type": "parking_results", "intent": intent.model_dump(), "count": len(slots), "slots": [slot.model_dump() for slot in slots]}
    return state


def build_host_graph():
    graph = StateGraph(HostAgentState)
    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("clarification", clarification_node)
    graph.add_node("discover_providers", discover_providers_node)
    graph.add_node("call_providers", call_providers_node)
    graph.add_node("rank_slots", rank_slots_node)
    graph.add_node("build_response", build_response_node)
    graph.set_entry_point("parse_intent")
    graph.add_conditional_edges("parse_intent", should_continue_after_intent, {"clarify": "clarification", "discover": "discover_providers"})
    graph.add_edge("clarification", END)
    graph.add_edge("discover_providers", "call_providers")
    graph.add_edge("call_providers", "rank_slots")
    graph.add_edge("rank_slots", "build_response")
    graph.add_edge("build_response", END)
    return graph.compile()


host_graph = build_host_graph()


def run_host_agent(user_message: str) -> dict:
    logger.info("host_graph_started")
    result = host_graph.invoke({"user_message": user_message})
    logger.info("host_graph_completed response_type=%s count=%s", result["response"].get("type"), result["response"].get("count"))
    return result["response"]
