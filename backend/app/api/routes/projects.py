"""Project HTTP routes (first_revision phase 1).

Project CRUD plus seed read/rebuild. The route layer only does HTTP mapping;
lifecycle and sub-graph creation are delegated to project_service.
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
    """List all projects (project library cards)."""
    return list_projects()


@router.post("", response_model=ProjectDetailPayload)
async def add_project(payload: ProjectCreateRequest) -> ProjectDetailPayload:
    """Create a project, automatically creating its three sub-graphs."""
    return create_project(payload)


@router.get("/{project_id}", response_model=ProjectDetailPayload)
async def read_project(project_id: str) -> ProjectDetailPayload:
    """Project details (including the three graph_ids and the latest seed)."""
    return get_project_detail(project_id)


@router.patch("/{project_id}", response_model=ProjectDetailPayload)
async def patch_project(project_id: str, payload: ProjectUpdateRequest) -> ProjectDetailPayload:
    """Update the project's name / description (used to edit the brief on the project overview page)."""
    return update_project(project_id, payload)


@router.delete("/{project_id}", status_code=204)
async def remove_project(project_id: str) -> None:
    """Cascade-delete a project."""
    delete_project(project_id)


@router.get("/{project_id}/staging", response_model=list[AgentStagingBatchPayload])
async def read_project_staging(
    project_id: str, status: str | None = "pending"
) -> list[AgentStagingBatchPayload]:
    """List staging by project (defaults to pending only), so ChatWorkspace can show the entities extracted in the background in real time."""
    return list_project_staging(project_id, status)


@router.get("/{project_id}/nodes/{node_id}/fields", response_model=NodeFieldsPayload)
async def read_node_fields(project_id: str, node_id: str) -> NodeFieldsPayload:
    """Read the free-form fields of a character card."""
    return get_node_fields(project_id, node_id)


@router.put("/{project_id}/nodes/{node_id}/fields", response_model=NodeFieldsPayload)
async def replace_node_fields(
    project_id: str, node_id: str, payload: NodeFieldsPayload
) -> NodeFieldsPayload:
    """Wholesale replace the character card's free-form fields, persisting to the node.meta JSON."""
    return set_node_fields(project_id, node_id, payload.fields)


@router.post("/{project_id}/workspace_chat")
async def workspace_chat(project_id: str, payload: WorkspaceChatRequest) -> StreamingResponse:
    """Workspace bottom chat box: SSE stream of the passive Inspiration agent (W5)."""
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
    """Return where this node is referenced in other sub-graphs (used by the character card's back-reference section)."""
    return get_node_cross_references(project_id, node_id)


@router.get("/{project_id}/seed", response_model=ProjectSeedPayload)
async def read_project_seed(project_id: str) -> ProjectSeedPayload:
    """Read the project's current seed; returns 404 when no seed exists yet."""
    seed = get_latest_seed(project_id)
    if seed is None:
        raise HTTPException(status_code=404, detail="Seed not found")
    return seed


@router.post("/{project_id}/seed/rebuild", response_model=ProjectSeedPayload)
async def rebuild_project_seed(project_id: str) -> ProjectSeedPayload:
    """Force a rebuild of the project seed, incrementing the version (placeholder in phase 1, wired to the compressor in phase 5)."""
    return rebuild_seed(project_id)
