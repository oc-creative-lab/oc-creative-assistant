"""LangGraph shared state definition.

The agent graph flows around this ``AgentState``: load_context writes the
project and session snapshot, intent_router decides this turn's intent, RAG and
the corresponding agent drop their results into their own fields, and the
assembler and persistence hub take the matching agent's output by intent for
post-processing.

All fields use ``total=False``, so local tests can construct only the subset
they care about to start a single node.
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
    """The state dict shared between LangGraph nodes."""

    session_id: str
    project_id: str
    user_message: str
    selected_node_ids: list[str]
    preferred_intent: str

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

    # first_revision stage 4: background B-agents (structured_extractor / question_planner).
    # When extraction_enabled is off, both nodes are no-ops throughout, and the FloatingChatDock legacy flow is unaffected.
    extraction_enabled: bool
    web_search_mode: str
    seed_context: str
    next_question_hint: str
    deferred_fields: list[dict]
    extraction_batch_id: str | None
    extraction_count: int
    extraction_applied: list[dict]