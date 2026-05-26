"""LangGraph StateGraph 装配。

把 AgentState、节点和路由规则连成一张可执行图; 编译时绑定 SqliteSaver,
让同一 thread_id 的多次调用能继承之前的中间状态。

intent_router 决定本轮走哪个 agent, 由 conditional_edges 直接路由,
agent 跑完进 boundary_check 收口, 再 chat_assembler / persistence_hub /
summary_compress 依次执行。

START → load_context → intent_router → parallel_retrieval → context_compress
                                                                 │
                                                                 ▼
                                                      ┌──────┬──────┬──────┐
                                                      ▼      ▼      ▼      ▼
                                              inspiration research structure simulation
                                                      └──────┴──────┴──────┘
                                                                 │
                                                                 ▼
                                                        boundary_check
                                                                 │
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
from app.agents.nodes.research_agent import research_agent_node
from app.agents.nodes.simulation_agent import simulation_agent_node
from app.agents.nodes.structure_agent import structure_agent_node
from app.agents.nodes.summary_compress import summary_compress_node
from app.agents.state import AgentState

_AGENT_NODE_BY_INTENT: dict[str, str] = {
    "inspiration": "inspiration_agent",
    "research": "research_agent",
    "structure": "structure_agent",
    "simulation": "simulation_agent",
    "small_talk": "boundary_check",
}
"""按 intent.primary 路由到 agent 节点; small_talk 跳过 agent 直接进 boundary_check。"""

_AGENT_NODES: tuple[str, ...] = (
    "inspiration_agent",
    "research_agent",
    "structure_agent",
    "simulation_agent",
)


def _route_by_intent(state: AgentState) -> str:
    """conditional_edges 路由函数; intent 缺失时退到 boundary_check 兜底。"""
    intent = state.get("intent")
    if intent is None:
        return "boundary_check"
    return _AGENT_NODE_BY_INTENT.get(intent.primary, "boundary_check")


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
    builder.add_node("chat_assembler", chat_assembler_node)
    builder.add_node("persistence_hub", persistence_hub_node)
    builder.add_node("summary_compress", summary_compress_node)

    builder.add_edge(START, "load_context")
    builder.add_edge("load_context", "intent_router")
    builder.add_edge("intent_router", "parallel_retrieval")
    builder.add_edge("parallel_retrieval", "context_compress")

    builder.add_conditional_edges(
        "context_compress",
        _route_by_intent,
        {**{name: name for name in _AGENT_NODES}, "boundary_check": "boundary_check"},
    )
    for agent in _AGENT_NODES:
        builder.add_edge(agent, "boundary_check")

    builder.add_edge("boundary_check", "chat_assembler")
    builder.add_edge("chat_assembler", "persistence_hub")
    builder.add_edge("persistence_hub", "summary_compress")
    builder.add_edge("summary_compress", END)

    return builder


@lru_cache(maxsize=1)
def get_agent_graph():
    """单例编译图, 避免每次调用重建; checkpointer 在编译时绑定。"""
    return _build_graph().compile(checkpointer=get_checkpointer())