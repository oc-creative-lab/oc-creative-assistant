"""Project HTTP 路由（first_revision 阶段 1）。

项目 CRUD + 种子读取/重建。路由层只做 HTTP 映射，生命周期与 sub-graph 创建
交给 project_service。
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import (
    AgentStagingBatchPayload,
    CrossReferenceResponse,
    NodeFieldsPayload,
    ProjectCreateRequest,
    ProjectDetailPayload,
    ProjectSeedPayload,
    ProjectSummaryPayload,
    ProjectUpdateRequest,
    WorkspaceChatRequest,
)
from app.services.chat_service import list_project_staging
from app.services.cross_reference_service import get_node_cross_references
from app.services.node_fields_service import get_node_fields, set_node_fields
from app.services.workspace_chat_service import stream_workspace_chat
from app.services.project_service import (
    create_project,
    delete_project,
    get_latest_seed,
    get_project_detail,
    list_projects,
    rebuild_seed,
    update_project,
)


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectSummaryPayload])
async def read_projects() -> list[ProjectSummaryPayload]:
    """列出全部项目（项目库卡片）。"""
    return list_projects()


@router.post("", response_model=ProjectDetailPayload)
async def add_project(payload: ProjectCreateRequest) -> ProjectDetailPayload:
    """创建项目，自动创建三个 sub-graph。"""
    return create_project(payload)


@router.get("/{project_id}", response_model=ProjectDetailPayload)
async def read_project(project_id: str) -> ProjectDetailPayload:
    """项目详情（含三个 graph_id 与最新种子）。"""
    return get_project_detail(project_id)


@router.patch("/{project_id}", response_model=ProjectDetailPayload)
async def patch_project(project_id: str, payload: ProjectUpdateRequest) -> ProjectDetailPayload:
    """更新项目 name / description（项目概览页编辑简介用）。"""
    return update_project(project_id, payload)


@router.delete("/{project_id}", status_code=204)
async def remove_project(project_id: str) -> None:
    """级联删除项目。"""
    delete_project(project_id)


@router.get("/{project_id}/staging", response_model=list[AgentStagingBatchPayload])
async def read_project_staging(
    project_id: str, status: str | None = "pending"
) -> list[AgentStagingBatchPayload]:
    """按项目列出 staging（默认只看待审），供 ChatWorkspace 实时展示后台抽出的实体。"""
    return list_project_staging(project_id, status)


@router.get("/{project_id}/nodes/{node_id}/fields", response_model=NodeFieldsPayload)
async def read_node_fields(project_id: str, node_id: str) -> NodeFieldsPayload:
    """读取角色卡自由字段。"""
    return get_node_fields(project_id, node_id)


@router.put("/{project_id}/nodes/{node_id}/fields", response_model=NodeFieldsPayload)
async def replace_node_fields(
    project_id: str, node_id: str, payload: NodeFieldsPayload
) -> NodeFieldsPayload:
    """整体替换角色卡自由字段，持久化到 node.meta JSON。"""
    return set_node_fields(project_id, node_id, payload.fields)


@router.post("/{project_id}/workspace_chat")
async def workspace_chat(project_id: str, payload: WorkspaceChatRequest) -> StreamingResponse:
    """工作台底部对话框：被动灵感 agent 的 SSE 流（W5）。"""
    return StreamingResponse(
        stream_workspace_chat(project_id, payload.message, payload.quoted_node_ids),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/{project_id}/nodes/{node_id}/cross_references",
    response_model=CrossReferenceResponse,
)
async def read_node_cross_references(
    project_id: str, node_id: str
) -> CrossReferenceResponse:
    """返回该节点在其它 sub-graph 中被引用的位置（角色卡反向引用区用）。"""
    return get_node_cross_references(project_id, node_id)


@router.get("/{project_id}/seed", response_model=ProjectSeedPayload)
async def read_project_seed(project_id: str) -> ProjectSeedPayload:
    """读取项目当前种子；尚无种子时返回 404。"""
    seed = get_latest_seed(project_id)
    if seed is None:
        raise HTTPException(status_code=404, detail="Seed not found")
    return seed


@router.post("/{project_id}/seed/rebuild", response_model=ProjectSeedPayload)
async def rebuild_project_seed(project_id: str) -> ProjectSeedPayload:
    """强制重建项目种子，版本自增（阶段 1 为占位，阶段 5 接入压缩器）。"""
    return rebuild_seed(project_id)
