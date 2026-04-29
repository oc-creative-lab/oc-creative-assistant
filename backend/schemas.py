from pydantic import BaseModel, Field


# 项目的最小展示信息，前端用于标题栏和后续 graph 请求定位。
class ProjectPayload(BaseModel):
    # 数据库项目 id，前端后续用它定位要读取/保存的 graph。
    id: str
    # 项目展示名，只用于 UI 展示，不参与 graph 关联。
    name: str


# Vue Flow 使用二维坐标定位节点；后端只持久化业务需要的 x/y。
class PositionPayload(BaseModel):
    # Vue Flow 节点在画布坐标系中的横坐标。
    x: float
    # Vue Flow 节点在画布坐标系中的纵坐标。
    y: float


# 前后端共享的节点 DTO。字段名保持前端习惯，避免在 API 边界频繁转换。
class NodePayload(BaseModel):
    # Vue Flow node id，同时也是后端 nodes 表主键。
    id: str
    # 节点业务类型；为了兼容前端 Vue Flow，字段名仍保留为 type。
    type: str
    # nodeType 与 type 保持同义，前端 data 中保留一份，便于详情面板编辑和持久化恢复。
    nodeType: str | None = None
    title: str
    # 节点正文内容，RAG 和详情面板都会读取它。
    content: str
    # 前端画布位置；后端会拆成 position_x/position_y 两列保存。
    position: PositionPayload
    # 当前 meta 在 API 层仍是字符串；数据库内部会包装成 JSON，给后续扩展留空间。
    meta: str = ""
    # 展示用类型标签，例如“角色”“世界观”“剧情”，不参与节点类型判断。
    typeLabel: str = ""
    # tags/status 先存入节点 meta JSON，PoC 阶段不额外扩表。
    tags: list[str] = Field(default_factory=list)
    status: str = "draft"


# Vue Flow 边 DTO，保留 handle 和边样式信息，保证保存后连线能按原样恢复。
class EdgePayload(BaseModel):
    # Vue Flow edge id，同时也是后端 edges 表主键。
    id: str
    # 起点节点 id，对应 Vue Flow edge.source 和 ORM source 字段。
    source: str
    # 终点节点 id，对应 Vue Flow edge.target 和 ORM target 字段。
    target: str
    # 连接线上展示的文案；为空时服务层会使用默认“关联”。
    label: str = ""
    # 创作关系类型，用于区分因果、引用、归属等语义关系。
    relationType: str = "relates_to"
    # 起点连接桩 id；保存后可让 Vue Flow 还原到同一个 handle。
    sourceHandle: str | None = None
    # 终点连接桩 id；保存后可让 Vue Flow 还原到同一个 handle。
    targetHandle: str | None = None
    # Vue Flow 边的渲染类型，例如 smoothstep。
    type: str = "smoothstep"
    # 是否启用 Vue Flow 边动画。
    animated: bool = False


# 读取 graph 时返回项目元信息与完整节点/边快照。
class GraphPayload(BaseModel):
    project: ProjectPayload
    nodes: list[NodePayload]
    edges: list[EdgePayload]


# 保存接口采用整图快照替换策略；空列表允许清空当前项目 graph。
class SaveGraphRequest(BaseModel):
    nodes: list[NodePayload] = Field(default_factory=list)
    edges: list[EdgePayload] = Field(default_factory=list)


# PATCH 节点时所有字段都可选，None 表示不修改该字段。
class UpdateNodeRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    position: PositionPayload | None = None
    nodeType: str | None = None
    meta: str | None = None
    typeLabel: str | None = None
    tags: list[str] | None = None
    status: str | None = None


# RAG 上下文预览请求：当前只构造上下文和 prompt，不调用任何 LLM。
class RagContextRequest(BaseModel):
    # 当前正在请求 AI 辅助的节点 id，服务端会据此找到同项目 graph。
    node_id: str
    # 用户输入的检索问题；为空时服务端用当前节点标题和内容作为 query。
    query: str = ""
    # Agent 类型预留字段；当前 PoC 只允许 inspiration。
    agent_type: str = "inspiration"
    # 向量检索最多返回多少条，服务层会限制在安全范围内。
    top_k: int = 5


# RAG 响应中的当前节点快照；前端用于展示“AI 正在围绕哪个节点思考”。
class RagCurrentNodePayload(BaseModel):
    id: str
    type: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)


# 由画布边推导出的一跳图关系上下文，优先级高于语义检索。
class RagGraphContextItem(BaseModel):
    id: str
    type: str
    title: str
    content: str
    # 来自 edge.label，帮助 Agent 理解两节点之间的自然语言关系。
    relation_label: str
    # 来自 edge.relation_type，保留结构化关系类型。
    relation_type: str
    # outgoing/incoming 表示当前节点在这条边中的方向。
    direction: str


# 向量检索命中的相似节点；score 越高表示和 query 越接近。
class RagVectorContextItem(BaseModel):
    id: str
    type: str
    title: str
    content: str
    score: float


# 合并后的上下文条目，用于避免 graph 与 vector 命中重复注入 prompt。
class RagMergedContextItem(BaseModel):
    id: str
    # graph/vector/both 标识上下文来源，方便前端调试排序和来源解释。
    source: str
    type: str
    title: str
    content: str


# 调试信息只返回构造过程状态，不代表真实 LLM 已被调用。
class RagDebugPayload(BaseModel):
    # 实际用于检索的 query，可能来自用户输入，也可能由当前节点内容兜底。
    query_used: str
    top_k: int
    # chroma/hash_memory_fallback 等标记，帮助判断当前走的是哪种检索路径。
    vector_store: str
    llm_called: bool = False
    # 向量库失败时记录错误文本，便于前端提示或开发排查。
    vector_error: str | None = None


# RAG 上下文接口的完整响应；prompt 只是预览，不会触发模型生成。
class RagContextResponse(BaseModel):
    current_node: RagCurrentNodePayload
    graph_context: list[RagGraphContextItem]
    vector_context: list[RagVectorContextItem]
    merged_context: list[RagMergedContextItem]
    prompt: str
    debug: RagDebugPayload
