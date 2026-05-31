"""LangGraph 共享状态定义。

agent 图围绕这份 ``AgentState`` 流转: load_context 写入项目和会话快照,
intent_router 决定本轮 intent, RAG 与对应 agent 把结果落到各自字段,
装配器与持久化中枢按 intent 取对应 agent 的输出做后处理。

所有字段都用 ``total=False``, 让局部测试可以只构造关心的子集启动单节点。
"""

from __future__ import annotations

from typing import TypedDict

from app.agents.schemas import (
    ChatAssemblerOutput,
    InspirationOutput,
    IntentClassification,
    ResearchOutput,
    SimulationOutput,
    StructureOutput,
)
from app.schemas import (
    RagCurrentNodePayload,
    RagGraphContextItem,
    RagMergedContextItem,
    RagVectorContextItem,
)


class AgentState(TypedDict, total=False):
    """LangGraph 节点之间共享的状态字典。"""

    session_id: str
    project_id: str
    user_message: str
    selected_node_ids: list[str]

    world_brief: str
    conversation_summary: str
    key_facts: list[str]
    recent_messages: list[dict]

    intent: IntentClassification

    current_nodes: list[RagCurrentNodePayload]
    graph_context: list[RagGraphContextItem]
    vector_context: list[RagVectorContextItem]
    merged_context: list[RagMergedContextItem]

    inspiration_output: InspirationOutput
    research_output: ResearchOutput
    structure_output: StructureOutput
    simulation_output: SimulationOutput

    assembler_output: ChatAssemblerOutput

    boundary_warnings: list[str]

    assistant_message_id: str
    staging_batch_id: str | None
    staging_count: int

    # first_revision 阶段 4：后台 B-agent（structured_extractor / question_planner）。
    # extraction_enabled 关闭时两个节点全程 no-op，FloatingChatDock 旧流程不受影响。
    extraction_enabled: bool
    seed_context: str
    next_question_hint: str
    deferred_fields: list[dict]
    extraction_batch_id: str | None
    extraction_count: int
    extraction_applied: list[dict]