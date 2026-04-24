from pydantic import BaseModel, Field


class ProjectPayload(BaseModel):
    id: str
    name: str


class PositionPayload(BaseModel):
    x: float
    y: float


class NodePayload(BaseModel):
    id: str
    type: str
    title: str
    content: str
    position: PositionPayload
    meta: str = ""
    typeLabel: str = ""


class EdgePayload(BaseModel):
    id: str
    source: str
    target: str
    label: str = ""
    sourceHandle: str | None = None
    targetHandle: str | None = None
    type: str = "smoothstep"
    animated: bool = False


class GraphPayload(BaseModel):
    project: ProjectPayload
    nodes: list[NodePayload]
    edges: list[EdgePayload]


class SaveGraphRequest(BaseModel):
    nodes: list[NodePayload] = Field(default_factory=list)
    edges: list[EdgePayload] = Field(default_factory=list)


class UpdateNodeRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    position: PositionPayload | None = None
    meta: str | None = None
    typeLabel: str | None = None
