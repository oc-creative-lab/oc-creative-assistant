"""Pydantic DTOs for the backend API.

Field naming follows the existing frontend contract, to avoid structural migrations
changing the HTTP request and response formats. Conversion between internal database
fields and API fields is handled by the service layer.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectPayload(BaseModel):
    """Minimal display information for a project."""

    id: str
    name: str


class ProjectSeedPayload(BaseModel):
    """Project seed DTO (first_revision decision 3)."""

    id: str
    project_id: str
    version: int
    seed_json: str = ""
    source: str = "user_edit"
    created_at: datetime | None = None


class GraphInfoPayload(BaseModel):
    """Sub-graph metadata DTO."""

    id: str
    project_id: str
    section: Literal["plot", "character", "world"]


class ProjectSummaryPayload(BaseModel):
    """Overview information needed by the project library card."""

    id: str
    name: str
    description: str = ""
    cover_image: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectDetailPayload(BaseModel):
    """Project details: includes the three sub-graph ids and the latest seed (first_revision phase 1)."""

    id: str
    name: str
    description: str = ""
    cover_image: str = ""
    plot_graph_id: str | None = None
    character_graph_id: str | None = None
    world_graph_id: str | None = None
    latest_seed: ProjectSeedPayload | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectCreateRequest(BaseModel):
    """Create-project request body; the backend automatically creates three sub-graphs."""

    name: str
    description: str = ""


class ProjectUpdateRequest(BaseModel):
    """Partial project update request body; None means the field is not modified."""

    name: str | None = None
    description: str | None = None
    cover_image: str | None = None


class NodeFieldsPayload(BaseModel):
    """Node free-form fields DTO (first_revision decision 2)."""

    node_id: str
    fields: dict[str, str] = Field(default_factory=dict)


class WorkspaceChatRequest(BaseModel):
    """Request body for the workspace bottom chat box (second_revision change B / W5)."""

    message: str = ""
    quoted_node_ids: list[str] = Field(default_factory=list)


class CrossReferenceItem(BaseModel):
    """A single cross-sub-graph reference (first_revision phase 6)."""

    edge_id: str
    other_node_id: str
    other_title: str
    other_section: Literal["plot", "character", "world"]
    relation_type: str
    relation_label: str
    # 'outgoing': this node -> the other; 'incoming': the other -> this node
    direction: Literal["outgoing", "incoming"]


class CrossReferenceResponse(BaseModel):
    """All references to a node in other sub-graphs."""

    node_id: str
    section: Literal["plot", "character", "world"] | None = None
    references: list[CrossReferenceItem] = Field(default_factory=list)


class PositionPayload(BaseModel):
    """Two-dimensional node coordinates used by Vue Flow."""

    x: float
    y: float


class NodePayload(BaseModel):
    """Node DTO shared by frontend and backend.

    Field names follow frontend conventions, e.g. `type`, `nodeType`, and `typeLabel`,
    to avoid introducing extra mapping cost at the API boundary.
    """

    id: str
    type: str
    nodeType: str | None = None
    title: str
    content: str
    position: PositionPayload
    meta: str = ""
    typeLabel: str = ""
    tags: list[str] = Field(default_factory=list)
    status: str = "draft"
    parentId: str | None = None
    sortOrder: int = 0


class EdgeWaypointPayload(BaseModel):
    """Perpendicular coordinates of the edge midpoint produced by user dragging.

    Consistent with the frontend ``CreativeEdgeWaypoint``; fields keep camelCase to
    avoid DTO conversion noise.
    """

    orientation: str  # "horizontal" | "vertical"
    middle: float
    nearSource: float | None = None
    nearTarget: float | None = None


class EdgePayload(BaseModel):
    """Vue Flow edge DTO.

    Stores handle and edge styling information, so that after the backend reads it the
    frontend can restore the connections exactly as they were.
    """

    id: str
    source: str
    target: str
    label: str = ""
    relationType: str = "relates_to"
    sourceHandle: str | None = None
    targetHandle: str | None = None
    type: str = "smoothstep"
    animated: bool = False
    waypoint: EdgeWaypointPayload | None = None


class IndexingStatusPayload(BaseModel):
    """Vector index status DTO.

    The save endpoint first guarantees the write to SQLite, then carries the
    embedding/ChromaDB synchronization result back to the frontend, so the user can
    know whether semantic retrieval is actually available.
    """

    status: str = "not_checked"
    message: str = ""
    provider: str = ""
    model: str = ""
    dimension: int = 0
    expected_nodes: int = 0
    indexed_nodes: int = 0
    missing_node_ids: list[str] = Field(default_factory=list)
    error: str | None = None


class GraphPayload(BaseModel):
    """When reading the graph, returns project metadata and the full node and edge snapshots."""

    project: ProjectPayload
    nodes: list[NodePayload]
    edges: list[EdgePayload]
    indexing: IndexingStatusPayload = Field(default_factory=IndexingStatusPayload)


class SaveGraphRequest(BaseModel):
    """Save endpoint request body.

    The save strategy is a whole-graph snapshot replacement; empty lists mean clearing
    the current project graph.
    """

    nodes: list[NodePayload] = Field(default_factory=list)
    edges: list[EdgePayload] = Field(default_factory=list)


class UpdateNodeRequest(BaseModel):
    """Partial node update request body.

    All fields are optional; `None` means the field is not modified.
    """

    title: str | None = None
    content: str | None = None
    position: PositionPayload | None = None
    nodeType: str | None = None
    meta: str | None = None
    typeLabel: str | None = None
    tags: list[str] | None = None
    status: str | None = None


class RagContextRequest(BaseModel):
    """RAG context preview request.

    The current endpoint only builds the context and the prompt; it does not call any LLM.
    """

    node_id: str
    query: str = ""
    agent_type: str = "inspiration"
    top_k: int = 5


class RagCurrentNodePayload(BaseModel):
    """Snapshot of the current node in the RAG response."""

    id: str
    type: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    fields: dict[str, str] = Field(default_factory=dict)


class RagGraphContextItem(BaseModel):
    """One-hop graph relation context derived from canvas edges."""

    id: str
    type: str
    title: str
    content: str
    relation_label: str
    relation_type: str
    direction: str


class RagVectorContextItem(BaseModel):
    """A similar node hit by vector retrieval."""

    id: str
    type: str
    title: str
    content: str
    score: float


class RagMergedContextItem(BaseModel):
    """A merged context item."""

    id: str
    source: str
    type: str
    title: str
    content: str


class RagDebugPayload(BaseModel):
    """Debug information for RAG context construction."""

    query_used: str
    top_k: int
    vector_store: str
    llm_called: bool = False
    vector_error: str | None = None


class MemorySearchRequest(BaseModel):
    """Project-level Lore Memory search request."""

    query: str = ""
    node_type: str | None = None
    top_k: int = 6


class MemorySearchItem(BaseModel):
    """A hit item from a project-level Lore Memory search."""

    id: str
    type: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    status: str = "draft"
    score: float


class MemorySearchResponse(BaseModel):
    """Project-level Lore Memory search response."""

    items: list[MemorySearchItem]
    debug: RagDebugPayload


class RagContextResponse(BaseModel):
    """The full response of the RAG context endpoint."""

    current_node: RagCurrentNodePayload
    graph_context: list[RagGraphContextItem]
    vector_context: list[RagVectorContextItem]
    merged_context: list[RagMergedContextItem]
    prompt: str
    debug: RagDebugPayload


class ChatSessionCreateRequest(BaseModel):
    """Request body for creating a chat session."""

    project_id: str
    title: str = ""


class ChatSessionPayload(BaseModel):
    """Chat session DTO."""

    id: str
    project_id: str
    thread_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class SessionRenameRequest(BaseModel):
    """Request body for renaming a chat session."""
    title: str


class SessionTitleRequest(BaseModel):
    """Request body for LLM-summarized session title generation."""
    user_message: str

    
class ChatMessageCreateRequest(BaseModel):
    """Request body for appending a chat message; from Phase 4 on, the graph entry point replaces the direct POST."""

    role: Literal["user", "assistant", "system"]
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)


class ChatMessagePayload(BaseModel):
    """Chat message DTO."""

    id: str
    session_id: str
    role: str
    content: str
    meta: dict[str, Any]
    created_at: datetime


class AgentStagingCreateItem(BaseModel):
    """Write payload for a single staging item; used by both persistence_hub and the manual endpoint."""

    change_type: Literal[
        "create_node",
        "create_edge",
        "update_node",
        "delete_node",
        "delete_edge",
    ]
    target_id: str | None = None
    pending_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""


class AgentStagingBatchCreateRequest(BaseModel):
    """Request body for writing a batch of staging items in the same Agent turn."""

    message_id: str
    agent_type: str = ""
    items: list[AgentStagingCreateItem] = Field(default_factory=list)


class AgentStagingPayload(BaseModel):
    """DTO for a single staging item."""

    id: str
    session_id: str
    message_id: str
    project_id: str
    batch_id: str
    change_type: str
    target_id: str | None
    pending_id: str | None
    payload: dict[str, Any]
    payload_edited: dict[str, Any] | None
    agent_type: str
    reasoning: str
    order_in_batch: int
    status: str
    created_at: datetime
    resolved_at: datetime | None


class AgentStagingBatchPayload(BaseModel):
    """Staging batch DTO; aggregates multiple changes sharing the same batch_id for display."""

    batch_id: str
    items: list[AgentStagingPayload]


class AgentStagingActionRequest(BaseModel):
    """Request for handling a single staging item.

    ``payload_edited`` is required when ``action='edit'``; it is ignored for other actions.
    """

    action: Literal["accept", "edit", "reject"]
    payload_edited: dict[str, Any] | None = None


class AgentStagingBatchActionRequest(BaseModel):
    """Request for batch staging handling."""

    action: Literal["accept_all", "reject_all"]


class ChatRequest(BaseModel):
    """Request body for triggering agent_graph inference."""

    session_id: str
    user_message: str
    selected_node_ids: list[str] = Field(default_factory=list)
    # first_revision phase 4: ChatWorkspace full-screen chat sets this to True to enable the background B-agent;
    # FloatingChatDock does not pass it, keeping the old flow (no question_planner / structured_extractor side effects).
    extraction_enabled: bool = False
    # auto: heuristic decides; on: force Tavily; off: never call web_search this turn.
    web_search_mode: Literal["auto", "on", "off"] = "auto"
    # User-selected agent mode; "auto" lets intent_router classify freely.
    preferred_intent: Literal["auto", "research", "inspiration", "structure"] = "auto"


class ChatResponse(BaseModel):
    """The chat reply after one round of agent inference, plus a side-effect summary.

    ``batch_id`` has a value only when this round produces staging; the frontend uses
    it to fetch the content of the staging panel.
    """

    message_id: str
    reply_text: str
    cited_node_ids: list[str] = Field(default_factory=list)
    intent: str
    batch_id: str | None
    staging_count: int
    staging_summary: str = ""