"""后端 API 的 Pydantic DTO。

字段命名以现有前端契约为准，避免结构迁移改变 HTTP 请求和响应格式。
数据库内部字段和 API 字段的转换由服务层完成。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectPayload(BaseModel):
    """项目的最小展示信息。"""

    id: str
    name: str


class ProjectSeedPayload(BaseModel):
    """项目种子 DTO（first_revision 决策 3）。"""

    id: str
    project_id: str
    version: int
    seed_json: str = ""
    source: str = "user_edit"
    created_at: datetime | None = None


class GraphInfoPayload(BaseModel):
    """sub-graph 元信息 DTO。"""

    id: str
    project_id: str
    section: Literal["plot", "character", "world"]


class ProjectSummaryPayload(BaseModel):
    """项目库卡片所需的概览信息。"""

    id: str
    name: str
    description: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectDetailPayload(BaseModel):
    """项目详情：含三个 sub-graph id 与最新种子（first_revision 阶段 1）。"""

    id: str
    name: str
    description: str = ""
    plot_graph_id: str | None = None
    character_graph_id: str | None = None
    world_graph_id: str | None = None
    latest_seed: ProjectSeedPayload | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectCreateRequest(BaseModel):
    """创建项目请求体；后端会自动创建三个 sub-graph。"""

    name: str
    description: str = ""


class ProjectUpdateRequest(BaseModel):
    """项目局部更新请求体；None 表示不修改该字段。"""

    name: str | None = None
    description: str | None = None


class NodeFieldsPayload(BaseModel):
    """节点自由字段 DTO（first_revision 决策 2）。"""

    node_id: str
    fields: dict[str, str] = Field(default_factory=dict)


class WorkspaceChatRequest(BaseModel):
    """工作台底部对话框请求体（second_revision 改点 B / W5）。"""

    message: str = ""
    quoted_node_ids: list[str] = Field(default_factory=list)


class CrossReferenceItem(BaseModel):
    """一条跨 sub-graph 引用（first_revision 阶段 6）。"""

    edge_id: str
    other_node_id: str
    other_title: str
    other_section: Literal["plot", "character", "world"]
    relation_type: str
    relation_label: str
    # 'outgoing': 本节点 → 对方; 'incoming': 对方 → 本节点
    direction: Literal["outgoing", "incoming"]


class CrossReferenceResponse(BaseModel):
    """某节点在其它 sub-graph 中的全部引用。"""

    node_id: str
    section: Literal["plot", "character", "world"] | None = None
    references: list[CrossReferenceItem] = Field(default_factory=list)


class PositionPayload(BaseModel):
    """Vue Flow 使用的二维节点坐标。"""

    x: float
    y: float


class NodePayload(BaseModel):
    """前后端共享的节点 DTO。

    字段名保持前端习惯，例如 `type`、`nodeType` 和 `typeLabel`，避免在 API
    边界引入额外映射成本。
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


class EdgeWaypointPayload(BaseModel):
    """用户拖拽产生的边中段 perp 坐标。

    跟前端 ``CreativeEdgeWaypoint`` 一致, 字段保留 camelCase 避免 DTO 转换噪声。
    """

    orientation: str  # "horizontal" | "vertical"
    middle: float
    nearSource: float | None = None
    nearTarget: float | None = None


class EdgePayload(BaseModel):
    """Vue Flow 边 DTO。

    保存 handle 和边样式信息，保证后端读取后前端能按原样恢复连线。
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
    """向量索引状态 DTO。

    保存接口会先保证 SQLite 落库，再把 embedding/ChromaDB 同步结果带给前端，
    这样用户能知道语义检索是否真的可用。
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
    """读取 graph 时返回项目元信息与完整节点、边快照。"""

    project: ProjectPayload
    nodes: list[NodePayload]
    edges: list[EdgePayload]
    indexing: IndexingStatusPayload = Field(default_factory=IndexingStatusPayload)


class SaveGraphRequest(BaseModel):
    """保存接口请求体。

    保存策略是整图快照替换；空列表表示清空当前项目 graph。
    """

    nodes: list[NodePayload] = Field(default_factory=list)
    edges: list[EdgePayload] = Field(default_factory=list)


class UpdateNodeRequest(BaseModel):
    """节点局部更新请求体。

    所有字段都可选；`None` 表示不修改该字段。
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
    """RAG 上下文预览请求。

    当前接口只构造上下文和 prompt，不调用任何 LLM。
    """

    node_id: str
    query: str = ""
    agent_type: str = "inspiration"
    top_k: int = 5


class RagCurrentNodePayload(BaseModel):
    """RAG 响应中的当前节点快照。"""

    id: str
    type: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)


class RagGraphContextItem(BaseModel):
    """由画布边推导出的一跳图关系上下文。"""

    id: str
    type: str
    title: str
    content: str
    relation_label: str
    relation_type: str
    direction: str


class RagVectorContextItem(BaseModel):
    """向量检索命中的相似节点。"""

    id: str
    type: str
    title: str
    content: str
    score: float


class RagMergedContextItem(BaseModel):
    """合并后的上下文条目。"""

    id: str
    source: str
    type: str
    title: str
    content: str


class RagDebugPayload(BaseModel):
    """RAG 上下文构造调试信息。"""

    query_used: str
    top_k: int
    vector_store: str
    llm_called: bool = False
    vector_error: str | None = None


class MemorySearchRequest(BaseModel):
    """项目级 Lore Memory 搜索请求。"""

    query: str = ""
    node_type: str | None = None
    top_k: int = 6


class MemorySearchItem(BaseModel):
    """项目级 Lore Memory 搜索命中项。"""

    id: str
    type: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    status: str = "draft"
    score: float


class MemorySearchResponse(BaseModel):
    """项目级 Lore Memory 搜索响应。"""

    items: list[MemorySearchItem]
    debug: RagDebugPayload


class RagContextResponse(BaseModel):
    """RAG 上下文接口的完整响应。"""

    current_node: RagCurrentNodePayload
    graph_context: list[RagGraphContextItem]
    vector_context: list[RagVectorContextItem]
    merged_context: list[RagMergedContextItem]
    prompt: str
    debug: RagDebugPayload


class ChatSessionCreateRequest(BaseModel):
    """创建对话会话的请求体。"""

    project_id: str
    title: str = ""


class ChatSessionPayload(BaseModel):
    """对话会话 DTO。"""

    id: str
    project_id: str
    thread_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageCreateRequest(BaseModel):
    """追加对话消息的请求体, Phase 4 起由 graph 入口取代直接 POST。"""

    role: Literal["user", "assistant", "system"]
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)


class ChatMessagePayload(BaseModel):
    """对话消息 DTO。"""

    id: str
    session_id: str
    role: str
    content: str
    meta: dict[str, Any]
    created_at: datetime


class AgentStagingCreateItem(BaseModel):
    """单条 staging 的写入载荷, persistence_hub 与手动接口都使用该结构。"""

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
    """同一 Agent turn 写入一批 staging 的请求体。"""

    message_id: str
    agent_type: str = ""
    items: list[AgentStagingCreateItem] = Field(default_factory=list)


class AgentStagingPayload(BaseModel):
    """staging 单项 DTO。"""

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
    """staging 批次 DTO, 把同一 batch_id 的多条变更聚合展示。"""

    batch_id: str
    items: list[AgentStagingPayload]


class AgentStagingActionRequest(BaseModel):
    """单条 staging 处理请求。

    ``action='edit'`` 时 ``payload_edited`` 必填; 其它 action 下被忽略。
    """

    action: Literal["accept", "edit", "reject"]
    payload_edited: dict[str, Any] | None = None


class AgentStagingBatchActionRequest(BaseModel):
    """批量 staging 处理请求。"""

    action: Literal["accept_all", "reject_all"]


class ChatRequest(BaseModel):
    """触发 agent_graph 推理的请求体。"""

    session_id: str
    user_message: str
    selected_node_ids: list[str] = Field(default_factory=list)
    # first_revision 阶段 4：ChatWorkspace 全屏聊天置 True 开启后台 B-agent；
    # FloatingChatDock 不传，保持旧流程（无 question_planner / structured_extractor 副作用）。
    extraction_enabled: bool = False


class ChatResponse(BaseModel):
    """agent 一轮推理后的对话回复 + 副作用摘要。

    ``batch_id`` 仅当本轮产出 staging 时有值, 前端凭它去拉 staging 面板的内容。
    """

    message_id: str
    reply_text: str
    cited_node_ids: list[str] = Field(default_factory=list)
    intent: str
    batch_id: str | None
    staging_count: int
    staging_summary: str = ""