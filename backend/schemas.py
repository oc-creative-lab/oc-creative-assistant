from pydantic import BaseModel, Field


# 项目的最小展示信息，前端用于标题栏和后续 graph 请求定位。
class ProjectPayload(BaseModel):
    id: str
    name: str


# Vue Flow 使用二维坐标定位节点；后端只持久化业务需要的 x/y。
class PositionPayload(BaseModel):
    x: float
    y: float


# 前后端共享的节点 DTO。字段名保持前端习惯，避免在 API 边界频繁转换。
class NodePayload(BaseModel):
    id: str
    type: str
    # nodeType 与 type 保持同义，前端 data 中保留一份，便于详情面板编辑和持久化恢复。
    nodeType: str | None = None
    title: str
    content: str
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
    id: str
    source: str
    target: str
    label: str = ""
    relationType: str = "relates_to"
    sourceHandle: str | None = None
    targetHandle: str | None = None
    type: str = "smoothstep"
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
