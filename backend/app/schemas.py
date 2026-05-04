"""后端 API 的 Pydantic DTO。

字段命名以现有前端契约为准，避免结构迁移改变 HTTP 请求和响应格式。
数据库内部字段和 API 字段的转换由服务层完成。
"""

from pydantic import BaseModel, Field


class ProjectPayload(BaseModel):
    """项目的最小展示信息。"""

    id: str
    name: str


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
