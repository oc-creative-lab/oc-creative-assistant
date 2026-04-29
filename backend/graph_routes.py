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


# Graph API 统一挂在 /api 下，路由层只做 HTTP 映射，业务和持久化规则放在 graph_store。
router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/projects/default", response_model=ProjectPayload)
async def read_default_project() -> ProjectPayload:
    """返回默认项目；首次调用会自动创建项目和示例 graph。"""
    # 请求不需要 body；返回的项目 id 会被前端继续用于读取/保存 graph。
    return ensure_default_project()


@router.get("/projects/{project_id}/graph", response_model=GraphPayload)
async def read_project_graph(project_id: str) -> GraphPayload:
    """读取指定项目下的全部 nodes / edges。"""
    # project_id 来自路径参数；项目不存在时服务层会抛 404。
    # 响应保持 Vue Flow 需要的 nodes/edges DTO 结构，前端可直接恢复画布。
    return get_project_graph(project_id)


@router.put("/projects/{project_id}/graph", response_model=GraphPayload)
async def replace_project_graph(project_id: str, payload: SaveGraphRequest) -> GraphPayload:
    """保存当前画布快照，整体替换该项目 graph。"""
    # payload 来自请求体，包含前端当前完整 nodes/edges 快照。
    # 保存失败的 400/404 由 graph_store 统一抛出，避免路由层重复业务校验。
    return save_project_graph(project_id, payload)


@router.post("/projects/{project_id}/nodes", response_model=NodePayload)
async def add_node(project_id: str, payload: NodePayload) -> NodePayload:
    """创建单个 node，先提供 API 能力，前端当前仍以整体保存为主。"""
    # 请求体就是单个 Vue Flow node 的后端 DTO；当前实现会 merge，允许覆盖同 id 节点。
    return create_node(project_id, payload)


@router.patch("/projects/{project_id}/nodes/{node_id}", response_model=NodePayload)
async def patch_node(project_id: str, node_id: str, payload: UpdateNodeRequest) -> NodePayload:
    """更新 node 的基础字段或位置。"""
    # node_id/project_id 来自路径，payload 中 None 表示“不修改该字段”。
    # 返回更新后的节点 DTO，便于前端用服务端最终结果刷新本地状态。
    return update_node(project_id, node_id, payload)


@router.post("/projects/{project_id}/edges", response_model=EdgePayload)
async def add_edge(project_id: str, payload: EdgePayload) -> EdgePayload:
    """创建单个 edge，保留给后续更细粒度的画布保存。"""
    # 请求体包含 source/target/sourceHandle/targetHandle；服务层校验端点属于同项目。
    return create_edge(project_id, payload)
