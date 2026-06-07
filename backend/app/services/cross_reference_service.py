"""Cross sub-graph reference service (first_revision phase 6).

EdgeORM only carries project_id (not graph_id), so an edge can naturally connect
two nodes in different sub-graphs (valid as long as they are in the same project,
guaranteed by graph_validation's project-level check). This module aggregates the
edges that "touch a given node and whose other end lands in a different
sub-graph", to support the back-reference section of a character card (e.g.
"Xiaoming appears in plot:Chapter 1 Encounter / belongs to world:Flame Kingdom").
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import or_, select

from app.db.database import SessionLocal
from app.db.models import EdgeORM, NodeORM, ProjectORM
from app.schemas import CrossReferenceItem, CrossReferenceResponse
from app.services.graph_repository import require_project


def _section_by_graph_id(project: ProjectORM) -> dict[str, str]:
    """The project's graph_id -> section reverse-lookup table."""
    mapping: dict[str, str] = {}
    if project.plot_graph_id:
        mapping[project.plot_graph_id] = "plot"
    if project.character_graph_id:
        mapping[project.character_graph_id] = "character"
    if project.world_graph_id:
        mapping[project.world_graph_id] = "world"
    return mapping


def get_node_cross_references(project_id: str, node_id: str) -> CrossReferenceResponse:
    """Return all places where this node is referenced in other sub-graphs."""
    with SessionLocal() as db:
        project = require_project(db, project_id)
        node = db.get(NodeORM, node_id)
        if node is None or node.project_id != project_id:
            raise HTTPException(status_code=404, detail="Node not found")

        section_of = _section_by_graph_id(project)
        own_section = section_of.get(node.graph_id or "")

        edges = db.scalars(
            select(EdgeORM).where(
                EdgeORM.project_id == project_id,
                or_(EdgeORM.source == node_id, EdgeORM.target == node_id),
            )
        ).all()

        references: list[CrossReferenceItem] = []
        for edge in edges:
            is_outgoing = edge.source == node_id
            other_id = edge.target if is_outgoing else edge.source
            other = db.get(NodeORM, other_id)
            if other is None:
                continue
            other_section = section_of.get(other.graph_id or "")
            # Keep only cross sub-graph references (the other end is in a different section).
            if other_section is None or other_section == own_section:
                continue
            references.append(
                CrossReferenceItem(
                    edge_id=edge.id,
                    other_node_id=other.id,
                    other_title=other.title,
                    other_section=other_section,
                    relation_type=edge.relation_type or "relates_to",
                    relation_label=edge.label or "related",
                    direction="outgoing" if is_outgoing else "incoming",
                )
            )

        return CrossReferenceResponse(
            node_id=node_id,
            section=own_section,
            references=references,
        )
