"""LangGraph StateGraph 装配。

把 AgentState、节点和路由规则连成一张可执行图; 编译时绑定 SqliteSaver,
让同一 thread_id 的多次调用能继承之前的中间状态。

intent_router 之后做两段路由:
- 第一段 ``_route_after_intent``: small_talk 直奔 chat_assembler, 不打 chroma
  也不跑 agent; 其它四种实质意图进入完整的 retrieval + agent 流水线
- 第二段 ``_route_to_agent``: context_compress 之后按 intent 精确派发到对应 agent

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
}
"""仅四种"实质性"意图在此映射; small_talk 已经在 _route_after_intent 截走,
不会走到这一层路由, 因此表里不再包含它。"""

_AGENT_NODES: tuple[str, ...] = tuple(_AGENT_NODE_BY_INTENT.values())


def _route_after_intent(state: AgentState) -> str:
    """intent_router 之后的首次路由: small_talk 跳过 retrieval / agent。

    intent 缺失同样按 small_talk 兜底, 让闲聊型回复在 graph 内全程不打 chroma。
    """
    intent = state.get("intent")
    if intent is None or intent.primary == "small_talk":
        return "chat_assembler"
    return "parallel_retrieval"


def _route_to_agent(state: AgentState) -> str:
    """context_compress 之后的二次路由: 按 intent.primary 派发到具体 agent。

    走到这一层时 intent 一定是四种实质意图之一 (small_talk 在上游已截走);
    若 LLM 偶发返回新的、未登记的 primary, 退到 inspiration_agent 不让图崩。
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
    builder.add_node("chat_assembler", chat_assembler_node)
    builder.add_node("persistence_hub", persistence_hub_node)
    builder.add_node("summary_compress", summary_compress_node)

    builder.add_edge(START, "load_context")
    builder.add_edge("load_context", "intent_router")

    # 第一段路由: small_talk 跳过 retrieval / agent 直接进装配器
    builder.add_conditional_edges(
        "intent_router",
        _route_after_intent,
        {
            "chat_assembler": "chat_assembler",
            "parallel_retrieval": "parallel_retrieval",
        },
    )

    builder.add_edge("parallel_retrieval", "context_compress")

    # 第二段路由: 四种实质意图各走自己的 agent
    builder.add_conditional_edges(
        "context_compress",
        _route_to_agent,
        {name: name for name in _AGENT_NODES},
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