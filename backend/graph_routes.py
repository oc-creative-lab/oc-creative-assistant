from fastapi import APIRouter

from graph_store import (
    create_edge,
    create_node,
    ensure_default_project,
    get_project_graph,
    save_project_graph,
    update_node,
)
from schemas import EdgePayload, GraphPayload, NodePayload, ProjectPayload, SaveGraphRequest, UpdateNodeRequest


router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/projects/default", response_model=ProjectPayload)
async def read_default_project() -> ProjectPayload:
    """返回默认项目；首次调用会自动创建项目和示例 graph。"""
    return ensure_default_project()


@router.get("/projects/{project_id}/graph", response_model=GraphPayload)
async def read_project_graph(project_id: str) -> GraphPayload:
    """读取指定项目下的全部 nodes / edges。"""
    return get_project_graph(project_id)


@router.put("/projects/{project_id}/graph", response_model=GraphPayload)
async def replace_project_graph(project_id: str, payload: SaveGraphRequest) -> GraphPayload:
    """保存当前画布快照，整体替换该项目 graph。"""
    return save_project_graph(project_id, payload)


@router.post("/projects/{project_id}/nodes", response_model=NodePayload)
async def add_node(project_id: str, payload: NodePayload) -> NodePayload:
    """创建单个 node，先提供 API 能力，前端当前仍以整体保存为主。"""
    return create_node(project_id, payload)


@router.patch("/projects/{project_id}/nodes/{node_id}", response_model=NodePayload)
async def patch_node(project_id: str, node_id: str, payload: UpdateNodeRequest) -> NodePayload:
    """更新 node 的基础字段或位置。"""
    return update_node(project_id, node_id, payload)


@router.post("/projects/{project_id}/edges", response_model=EdgePayload)
async def add_edge(project_id: str, payload: EdgePayload) -> EdgePayload:
    """创建单个 edge，保留给后续更细粒度的画布保存。"""
    return create_edge(project_id, payload)
