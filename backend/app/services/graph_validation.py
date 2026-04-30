"""Graph 业务校验规则。

本模块属于服务层的业务规则边界，负责校验节点与边的项目一致性。
它不写数据库，也不决定 HTTP 路由结构。
"""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import NodeORM
from app.schemas import EdgePayload, NodePayload


def validate_edges_against_payload_nodes(nodes: list[NodePayload], edges: list[EdgePayload]) -> None:
    """校验整图快照中的边只引用本次提交的节点。

    Args:
        nodes: 本次保存提交的完整节点列表。
        edges: 本次保存提交的完整边列表。

    Raises:
        HTTPException: 当任一边引用当前 graph 外部节点时抛出。
    """
    node_ids = {node.id for node in nodes}
    invalid_edge = next(
        (edge for edge in edges if edge.source not in node_ids or edge.target not in node_ids),
        None,
    )

    if invalid_edge is not None:
        raise HTTPException(
            status_code=400,
            detail=f"Edge {invalid_edge.id} references a node outside current graph",
        )


def validate_edge_endpoints_in_project(
    session: Session,
    project_id: str,
    source: str,
    target: str,
) -> None:
    """校验单条边的两个端点都属于同一项目。

    Args:
        session: 当前数据库会话。
        project_id: 边所属项目 ID。
        source: 起点节点 ID。
        target: 终点节点 ID。

    Raises:
        HTTPException: 当端点缺失或端点不属于当前项目时抛出。
    """
    endpoint_count = session.scalar(
        select(func.count())
        .select_from(NodeORM)
        .where(
            NodeORM.project_id == project_id,
            NodeORM.id.in_([source, target]),
        )
    )

    if endpoint_count != 2:
        raise HTTPException(status_code=400, detail="Edge endpoints must belong to the same project")
