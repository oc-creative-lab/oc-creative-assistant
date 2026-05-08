"""LangGraph Agent 共享状态定义。

State 在节点之间传递数据, 是 RAG 检索结果与 Agent 输出的统一容器。
LangGraph 节点函数读取 / 部分更新这里的字段, conditional_edges 根据
agent_type 决定下一步路由, 实现 proposal 4.1.2 描述的非线性执行。
"""

from __future__ import annotations

from typing import Literal, TypedDict

from app.agents.schemas import InspirationOutput, ResearchOutput, StructureOutput
from app.schemas import (
    RagCurrentNodePayload,
    RagGraphContextItem,
    RagMergedContextItem,
    RagVectorContextItem,
)


AgentType = Literal["inspiration", "research", "structure"]


class AgentState(TypedDict, total=False):
    """LangGraph 共享状态。

    使用 total=False 是因为不同节点只填充自己关心的字段:
    - 检索节点不会写 final_output;
    - Agent 节点不需要写 graph_context;
    - Structure Agent 走 node_ids 多节点入口, inspiration / research 走 node_id。
    """

    # ---------- 输入 ----------
    project_id: str
    node_id: str | None
    node_ids: list[str]
    user_query: str
    agent_type: AgentType
    top_k: int

    # ---------- 检索阶段产出, 注入到 shared state(proposal 4.3.3) ----------
    current_node: RagCurrentNodePayload | None
    graph_context: list[RagGraphContextItem]
    # 按 node_type 分组, 让 Research / Structure 各取所需(proposal 3.1.3 三集合的逻辑等价)
    vector_context: dict[str, list[RagVectorContextItem]]
    merged_context: list[RagMergedContextItem]
    # 用于 proposal 7.3.4 的 2000 token cap 与 summary compression
    context_token_count: int

    # ---------- Agent 阶段产出 ----------
    final_output: InspirationOutput | ResearchOutput | StructureOutput | None
    # 任一节点遇到不可恢复错误时填写, 后续节点检测到 error 直接短路
    error: str | None