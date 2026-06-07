"""Vector index document extraction and lightweight DTO conversion.

The current index data source comes from canvas nodes. This module is responsible
for organizing ORM nodes into searchable text and providing the node DTO
conversion functions needed by RAG responses.
"""

from __future__ import annotations

from typing import Any

from app.db.models import NodeORM
from app.schemas import RagCurrentNodePayload, RagVectorContextItem
from app.services.graph_mappers import db_fields_to_api


def node_to_current_payload(node: NodeORM) -> RagCurrentNodePayload:
    """Convert an ORM node into the current-node RAG DTO.

    Args:
        node: The current node already read from SQLite.

    Returns:
        A current-node DTO containing only the fields needed by the prompt and the
        frontend preview.
    """
    return RagCurrentNodePayload(
        id=node.id,
        type=node.node_type,
        title=node.title,
        content=node.content,
        tags=db_tags_to_api(node.meta),
        fields=db_fields_to_api(node.meta),
    )


def node_to_vector_item(node: NodeORM, score: float) -> RagVectorContextItem:
    """Convert an ORM node into a vector retrieval result DTO.

    Args:
        node: The node hit by vector retrieval.
        score: The similarity score, usually between 0 and 1.

    Returns:
        A vector context response item; the score is rounded for easier frontend
        display.
    """
    content = (node.content or "").strip()
    fields = db_fields_to_api(node.meta)
    if fields:
        field_text = "; ".join(f"{key}: {value}" for key, value in fields.items())
        content = f"{content}\n{field_text}".strip() if content else field_text
    return RagVectorContextItem(
        id=node.id,
        type=node.node_type,
        title=node.title,
        content=content,
        score=round(score, 4),
    )


def node_to_document(node: NodeORM) -> str:
    """Assemble a node into a retrieval document for embedding.

    The title, type, tags, and content all participate in vectorization; the
    coordinates, sort order, and timestamps do not participate in retrieval
    semantics.

    Args:
        node: The ORM node to write or compare against during a query.

    Returns:
        The text used for the ChromaDB document and the Alibaba embedding.
    """
    tags = ", ".join(db_tags_to_api(node.meta))
    fields = db_fields_to_api(node.meta)
    fields_block = ""
    if fields:
        fields_block = "Fields:\n" + "\n".join(f"{key}: {value}" for key, value in fields.items())
    doc = f"""Title: {node.title}
Type: {node.node_type}
Tags: {tags}
Content:
{node.content}"""
    if fields_block:
        doc = f"{doc}\n{fields_block}"
    return doc


def db_tags_to_api(meta: Any) -> list[str]:
    """Read tags from a node's meta JSON.

    Args:
        meta: The meta field of the ORM node, which may come from an old database
            or manually edited data.

    Returns:
        A list of string tags; values of unexpected types are filtered out.
    """
    if isinstance(meta, dict):
        tags = meta.get("tags", [])
        return [tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else []

    return []


_node_to_current_payload = node_to_current_payload
_node_to_vector_item = node_to_vector_item
_node_to_document = node_to_document
_db_tags_to_api = db_tags_to_api
