"""LangGraph StateGraph assembly.

Wires AgentState, nodes, and routing rules into one executable graph; binds the
SqliteSaver at compile time so multiple calls with the same thread_id can
inherit the previously saved intermediate state.

Two routing stages follow intent_router:
- Stage 1 ``_route_after_intent``: small_talk goes straight to chat_assembler,
  hitting neither chroma nor any agent; the other four substantive intents
  enter the full retrieval + agent pipeline
- Stage 2 ``_route_to_agent``: after context_compress, dispatch precisely to the
  matching agent by intent

START → load_context → intent_router
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
           small_talk             else (4 intents)
                │                       ▼
                │              parallel_retrieval
                │                       │
                │                       ▼
                │               context_compress
                │                       │
                │             ┌─────────┼─────────┬───────────┐
                │             ▼         ▼         ▼           ▼
                │       inspiration  research  structure  simulation
                │             └─────────┴─────────┴───────────┘
                │                       │
                │                       ▼
                │                boundary_check
                │                       │
                └───────────┬───────────┘
                            ▼
                       chat_assembler
                            │
                            ▼
                      persistence_hub
                            │
                            ▼
                     summary_compress → END
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.agents.checkpointer import get_checkpointer
from app.agents.nodes.boundary_check import boundary_check_node
from app.agents.nodes.chat_assembler import chat_assembler_node
from app.agents.nodes.context_compress import context_compress_node
from app.agents.nodes.inspiration_agent import inspiration_agent_node
from app.agents.nodes.intent_router import intent_router_node
from app.agents.nodes.load_context import load_context_node
from app.agents.nodes.parallel_retrieval import parallel_retrieval_node
from app.agents.nodes.persistence_hub import persistence_hub_node
from app.agents.nodes.question_planner import question_planner_node
from app.agents.nodes.research_agent import research_agent_node
from app.agents.nodes.simulation_agent import simulation_agent_node
from app.agents.nodes.structure_agent import structure_agent_node
from app.agents.nodes.structured_extractor import structured_extractor_node
from app.agents.nodes.summary_compress import summary_compress_node
from app.agents.state import AgentState


_AGENT_NODE_BY_INTENT: dict[str, str] = {
    "inspiration": "inspiration_agent",
    "research": "research_agent",
    "structure": "structure_agent",
    "simulation": "simulation_agent",
}
"""Only the four "substantive" intents are mapped here; small_talk is already
intercepted in _route_after_intent and never reaches this routing layer, so it
is no longer included in the table."""

_AGENT_NODES: tuple[str, ...] = tuple(_AGENT_NODE_BY_INTENT.values())


def _route_after_intent(state: AgentState) -> str:
    """First routing after intent_router: small_talk skips retrieval / agent.

    A missing intent also falls back to small_talk, so chit-chat replies never
    hit chroma anywhere in the graph. Either path first passes through
    question_planner (which is a no-op when the gate is off), then enters
    chat_assembler.
    """
    intent = state.get("intent")
    if intent is None or intent.primary == "small_talk":
        return "question_planner"
    return "parallel_retrieval"


def _route_to_agent(state: AgentState) -> str:
    """Second routing after context_compress: dispatch to a concrete agent by intent.primary.

    By the time we reach this layer, intent is guaranteed to be one of the four
    substantive intents (small_talk was intercepted upstream); if the LLM
    occasionally returns a new, unregistered primary, fall back to
    inspiration_agent so the graph does not crash.
    """
    intent = state["intent"]
    return _AGENT_NODE_BY_INTENT.get(intent.primary, "inspiration_agent")


def _build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("load_context", load_context_node)
    builder.add_node("intent_router", intent_router_node)
    builder.add_node("parallel_retrieval", parallel_retrieval_node)
    builder.add_node("context_compress", context_compress_node)
    builder.add_node("inspiration_agent", inspiration_agent_node)
    builder.add_node("research_agent", research_agent_node)
    builder.add_node("structure_agent", structure_agent_node)
    builder.add_node("simulation_agent", simulation_agent_node)
    builder.add_node("boundary_check", boundary_check_node)
    # Background B-agents (first_revision decision 5): question_planner plans
    # follow-up questions before assembly, structured_extractor extracts
    # entities after persistence; both are no-ops when extraction_enabled is off.
    builder.add_node("question_planner", question_planner_node)
    builder.add_node("chat_assembler", chat_assembler_node)
    builder.add_node("persistence_hub", persistence_hub_node)
    builder.add_node("structured_extractor", structured_extractor_node)
    builder.add_node("summary_compress", summary_compress_node)

    builder.add_edge(START, "load_context")
    builder.add_edge("load_context", "intent_router")

    # Stage 1 routing: small_talk skips retrieval / agent, but still passes through question_planner first
    builder.add_conditional_edges(
        "intent_router",
        _route_after_intent,
        {
            "question_planner": "question_planner",
            "parallel_retrieval": "parallel_retrieval",
        },
    )

    builder.add_edge("parallel_retrieval", "context_compress")

    # Stage 2 routing: each of the four substantive intents goes to its own agent
    builder.add_conditional_edges(
        "context_compress",
        _route_to_agent,
        {name: name for name in _AGENT_NODES},
    )

    for agent in _AGENT_NODES:
        builder.add_edge(agent, "boundary_check")

    # Substantive intents: boundary_check → question_planner → chat_assembler
    builder.add_edge("boundary_check", "question_planner")
    builder.add_edge("question_planner", "chat_assembler")
    builder.add_edge("chat_assembler", "persistence_hub")
    # Extract in the background after persistence (without blocking the already-streamed reply), then compress the summary.
    builder.add_edge("persistence_hub", "structured_extractor")
    builder.add_edge("structured_extractor", "summary_compress")
    builder.add_edge("summary_compress", END)

    return builder


@lru_cache(maxsize=1)
def get_agent_graph():
    """Singleton compiled graph to avoid rebuilding on each call; the checkpointer is bound at compile time."""
    return _build_graph().compile(checkpointer=get_checkpointer())