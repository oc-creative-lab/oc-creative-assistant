"""跨 sub-graph 引用服务。

EdgeORM 只挂 project_id（不绑 graph_id），因此一条边天然可以连接不同 sub-graph
的两个节点（同一项目即合法，由 graph_validation 的项目级校验保证）。本模块把
“触达某节点、且另一端落在其它 sub-graph”的边汇总出来，支撑角色卡的反向引用区
（如“小明 出现在 plot:第一章相遇 / 所属 world:火焰王国”）。
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import or_, select

from app.db.database import SessionLocal
from app.db.models import EdgeORM, NodeORM, ProjectORM
from app.schemas import CrossReferenceItem, CrossReferenceResponse
from app.services.graph_repository import require_project


def _section_by_graph_id(project: ProjectORM) -> dict[str, str]:
    """项目的 graph_id → section 反查表。"""
    mapping: dict[str, str] = {}
    if project.plot_graph_id:
        mapping[project.plot_graph_id] = "plot"
    if project.character_graph_id:
        mapping[project.character_graph_id] = "character"
    if project.world_graph_id:
        mapping[project.world_graph_id] = "world"
    return mapping


def get_node_cross_references(project_id: str, node_id: str) -> CrossReferenceResponse:
    """返回该节点在其它 sub-graph 中被引用的所有位置。"""
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
            # 只保留跨 sub-graph 的引用（另一端在不同分区）。
            if other_section is None or other_section == own_section:
                continue
            references.append(
                CrossReferenceItem(
                    edge_id=edge.id,
                    other_node_id=other.id,
                    other_title=other.title,
                    other_section=other_section,
                    relation_type=edge.relation_type or "relates_to",
                    relation_label=edge.label or "关联",
                    direction="outgoing" if is_outgoing else "incoming",
                )
            )

        return CrossReferenceResponse(
            node_id=node_id,
            section=own_section,
            references=references,
        )
