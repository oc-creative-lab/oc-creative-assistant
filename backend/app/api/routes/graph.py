"""Graph HTTP routes.

The route layer only handles HTTP mapping and response model declarations;
business validation, persistence, and index synchronization are delegated to the
service layer.
"""

from fastapi import APIRouter

from app.schemas import (
    EdgePayload,
    GraphPayload,
    MemorySearchRequest,
    MemorySearchResponse,
    NodePayload,
    ProjectPayload,
    SaveGraphRequest,
    UpdateNodeRequest,
)
from app.services.graph_store import (
    create_edge,
    create_node,
    delete_node,
    ensure_default_project,
    get_project_graph,
    get_subgraph,
    save_project_graph,
    save_subgraph,
    update_node,
)
from app.services.rag_service import search_project_memory


router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/projects/default", response_model=ProjectPayload)
async def read_default_project() -> ProjectPayload:
    """Return the default project; the first call automatically creates the project and a sample graph."""
    return ensure_default_project()


@router.get("/graphs/{graph_id}", response_model=GraphPayload)
async def read_subgraph(graph_id: str) -> GraphPayload:
    """Read a snapshot of a single sub-graph (first_revision decision 1).

    Coexists with the per-project ``/projects/{id}/graph``: the old single-canvas
    workspace keeps using the project dimension, while the new three-view
    workspace loads plot / character / world separately by graph_id.
    """
    return get_subgraph(graph_id)


@router.put("/graphs/{graph_id}", response_model=GraphPayload)
async def replace_subgraph_route(graph_id: str, payload: SaveGraphRequest) -> GraphPayload:
    """Save a single sub-graph snapshot, wholesale replacing the sub-graph's nodes and internal edges."""
    return save_subgraph(graph_id, payload)


@router.get("/projects/{project_id}/graph", response_model=GraphPayload)
async def read_project_graph(project_id: str) -> GraphPayload:
    """Read the full graph snapshot under the given project."""
    return get_project_graph(project_id)


@router.put("/projects/{project_id}/graph", response_model=GraphPayload)
async def replace_project_graph(project_id: str, payload: SaveGraphRequest) -> GraphPayload:
    """Save the current canvas snapshot, wholesale replacing the project's graph."""
    return save_project_graph(project_id, payload)


@router.post("/projects/{project_id}/memory/search", response_model=MemorySearchResponse)
async def search_memory(project_id: str, payload: MemorySearchRequest) -> MemorySearchResponse:
    """Perform a Lore Memory semantic search within the given project."""
    return search_project_memory(project_id, payload)


@router.post("/projects/{project_id}/nodes", response_model=NodePayload)
async def add_node(project_id: str, payload: NodePayload) -> NodePayload:
    """Create or overwrite a single node, reserved for future fine-grained saving."""
    return create_node(project_id, payload)


@router.patch("/projects/{project_id}/nodes/{node_id}", response_model=NodePayload)
async def patch_node(project_id: str, node_id: str, payload: UpdateNodeRequest) -> NodePayload:
    """Update a node's basic fields or position."""
    return update_node(project_id, node_id, payload)


@router.delete("/projects/{project_id}/nodes/{node_id}", status_code=204)
async def remove_node(project_id: str, node_id: str) -> None:
    """Delete a single node and its related edges (used by the inline chat card's "undo/reject")."""
    delete_node(project_id, node_id)


@router.post("/projects/{project_id}/edges", response_model=EdgePayload)
async def add_edge(project_id: str, payload: EdgePayload) -> EdgePayload:
    """Create or overwrite a single edge, validating that both endpoint nodes belong to the same project."""
    return create_edge(project_id, payload)
