"""Public service entry point for RAG.

This module reads the graph snapshot of the project the current node belongs to,
coordinates graph relation retrieval, vector retrieval, and prompt assembly, and
returns the `RagContextResponse` needed by the API layer.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import EdgeORM, NodeORM, ProjectORM
from app.indexing.config import MAX_TOP_K
from app.indexing.document_loader import node_to_current_payload
from app.rag.prompts import build_inspiration_prompt
from app.rag.retrieval import build_graph_context, build_project_vector_context, merge_context
from app.schemas import (
    MemorySearchItem,
    MemorySearchRequest,
    MemorySearchResponse,
    RagContextRequest,
    RagContextResponse,
    RagDebugPayload,
)
from app.services.graph_mappers import db_status_to_api, db_tags_to_api


def build_rag_context(request: RagContextRequest) -> RagContextResponse:
    """Build the Hybrid RAG context preview.

    This function only returns the current node context, retrieval results, and the
    prompt; it does not call a real LLM. Vector index synchronization happens during
    the graph-save stage, so the query stage does not perform a full write into ChromaDB.

    Args:
        request: The RAG API request body.

    Returns:
        The current node, graph relation context, vector context, merged context,
        prompt, and debug information.

    Raises:
        HTTPException: Raised when the agent type is unsupported or the current node
            does not exist.
    """
    if request.agent_type != "inspiration":
        raise HTTPException(status_code=400, detail="Only inspiration agent is supported in this PoC")

    # Limit top_k to prevent a single request from injecting too many nodes into the prompt, which hurts debug readability and downstream LLM cost.
    top_k = max(1, min(request.top_k, MAX_TOP_K))

    with SessionLocal() as session:
        current_node = session.get(NodeORM, request.node_id)

        if current_node is None:
            raise HTTPException(status_code=404, detail="Node not found")

        project_id = current_node.project_id
        nodes = session.scalars(
            select(NodeORM).where(NodeORM.project_id == project_id).order_by(NodeORM.sort_order, NodeORM.created_at)
        ).all()
        edges = session.scalars(
            select(EdgeORM).where(EdgeORM.project_id == project_id).order_by(EdgeORM.sort_order, EdgeORM.created_at)
        ).all()

    current_payload = node_to_current_payload(current_node)
    query_used = request.query.strip() or f"{current_node.title}\n{current_node.content}".strip()
    graph_context = build_graph_context(current_node.id, nodes, edges)
    vector_context, vector_store, vector_error = build_project_vector_context(
        project_id, nodes, query_used, top_k + 1
    )
    vector_context = [item for item in vector_context if item.id != current_node.id][:top_k]
    merged_context = merge_context(graph_context, vector_context)
    prompt = build_inspiration_prompt(current_payload, graph_context, vector_context, query_used)

    return RagContextResponse(
        current_node=current_payload,
        graph_context=graph_context,
        vector_context=vector_context,
        merged_context=merged_context,
        prompt=prompt,
        debug=RagDebugPayload(
            query_used=query_used,
            top_k=top_k,
            vector_store=vector_store,
            llm_called=False,
            vector_error=vector_error,
        ),
    )


def search_project_memory(project_id: str, request: MemorySearchRequest) -> MemorySearchResponse:
    """Search the Lore Memory of the current project.

    This function only performs in-project vector retrieval and returns memory cards;
    it does not build a prompt nor call the LLM.

    Args:
        project_id: The current project ID.
        request: The project-level search criteria.

    Returns:
        The semantically related memory items within the current project and the
        debug status.

    Raises:
        HTTPException: Raised when the project does not exist.
    """
    top_k = max(1, min(request.top_k, MAX_TOP_K))
    query_used = request.query.strip()

    with SessionLocal() as session:
        project = session.get(ProjectORM, project_id)

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        nodes = session.scalars(
            select(NodeORM).where(NodeORM.project_id == project_id).order_by(NodeORM.sort_order, NodeORM.created_at)
        ).all()

    vector_context, vector_store, vector_error = build_project_vector_context(
        project_id,
        nodes,
        query_used,
        top_k,
        request.node_type,
    )
    node_by_id = {node.id: node for node in nodes}
    items: list[MemorySearchItem] = []

    for item in vector_context:
        node = node_by_id.get(item.id)

        if node is None:
            continue

        items.append(
            MemorySearchItem(
                id=node.id,
                type=node.node_type,
                title=node.title,
                content=node.content,
                tags=db_tags_to_api(node.meta),
                status=db_status_to_api(node.meta),
                score=item.score,
            )
        )

    return MemorySearchResponse(
        items=items,
        debug=RagDebugPayload(
            query_used=query_used,
            top_k=top_k,
            vector_store=vector_store,
            llm_called=False,
            vector_error=vector_error,
        ),
    )
