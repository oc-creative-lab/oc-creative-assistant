"""Graph 数据库操作 helper。

本模块属于服务层与 ORM 之间的持久化边界，负责项目、节点和边的数据库读写。
它不处理 HTTP 请求，也不触发 ChromaDB 同步；外部副作用由服务编排层在事务提交后执行。
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import EdgeORM, GraphORM, NodeORM, ProjectORM
from app.schemas import EdgePayload, NodePayload
from app.services.graph_mappers import edge_to_orm, node_to_orm
from app.services.graph_validation import validate_edges_against_payload_nodes


def require_project(session: Session, project_id: str) -> ProjectORM:
    """读取项目并确保项目存在。

    Args:
        session: 当前数据库会话。
        project_id: 项目 ID。

    Returns:
        匹配的项目 ORM 对象。

    Raises:
        HTTPException: 当项目不存在时抛出。
    """
    project = session.get(ProjectORM, project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


def read_ordered_nodes(session: Session, project_id: str) -> list[NodeORM]:
    """读取项目节点并按画布保存顺序排序。

    Args:
        session: 当前数据库会话。
        project_id: 项目 ID。

    Returns:
        当前项目的节点 ORM 列表。
    """
    return session.scalars(
        select(NodeORM)
        .where(NodeORM.project_id == project_id)
        .order_by(NodeORM.sort_order, NodeORM.created_at)
    ).all()


def read_ordered_edges(session: Session, project_id: str) -> list[EdgeORM]:
    """读取项目边并按画布保存顺序排序。

    Args:
        session: 当前数据库会话。
        project_id: 项目 ID。

    Returns:
        当前项目的边 ORM 列表。
    """
    return session.scalars(
        select(EdgeORM)
        .where(EdgeORM.project_id == project_id)
        .order_by(EdgeORM.sort_order, EdgeORM.created_at)
    ).all()


def read_project_nodes(project_id: str) -> list[NodeORM]:
    """读取项目节点快照。

    该函数会打开独立会话，供服务层在 SQLite 事务外对比向量索引 fingerprint。

    Args:
        project_id: 项目 ID。

    Returns:
        当前项目的节点 ORM 列表。
    """
    with SessionLocal() as session:
        return read_ordered_nodes(session, project_id)


def read_project_node(project_id: str, node_id: str) -> NodeORM | None:
    """读取单个节点快照。

    该函数在事务提交后重新读取节点，确保索引同步使用 SQLite 已落库状态。

    Args:
        project_id: 项目 ID。
        node_id: 节点 ID。

    Returns:
        匹配的节点 ORM；节点不存在或不属于项目时返回 None。
    """
    with SessionLocal() as session:
        node = session.get(NodeORM, node_id)

        if node is None or node.project_id != project_id:
            return None

        return node


def replace_graph(
    session: Session,
    project_id: str,
    nodes: list[NodePayload],
    edges: list[EdgePayload],
) -> None:
    """在当前事务中整体替换项目 graph。

    保存策略以完整快照为准：先校验边端点只引用本次提交的节点，再删除旧边和旧节点，
    最后按提交顺序写入新节点和新边。

    Args:
        session: 当前数据库事务会话。
        project_id: 项目 ID。
        nodes: 本次保存的完整节点列表。
        edges: 本次保存的完整边列表。

    Raises:
        HTTPException: 当边引用当前 graph 外部节点时抛出。
    """
    validate_edges_against_payload_nodes(nodes, edges)
    # SQLite 外键约束会阻止删除仍被边引用的节点，因此替换时必须先删除边。
    session.query(EdgeORM).filter(EdgeORM.project_id == project_id).delete(synchronize_session=False)
    session.query(NodeORM).filter(NodeORM.project_id == project_id).delete(synchronize_session=False)

    for index, node in enumerate(nodes):
        session.add(node_to_orm(project_id, node, index))

    for index, edge in enumerate(edges):
        session.add(edge_to_orm(project_id, edge, index))


# --- sub-graph 维度操作（first_revision 决策 1） ---


def require_graph(session: Session, graph_id: str) -> GraphORM:
    """读取 sub-graph 并确保存在。

    Raises:
        HTTPException: 当 sub-graph 不存在时抛出 404。
    """
    graph = session.get(GraphORM, graph_id)

    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not found")

    return graph


def read_ordered_nodes_by_graph(session: Session, graph_id: str) -> list[NodeORM]:
    """读取某个 sub-graph 的节点，按画布保存顺序排序。"""
    return session.scalars(
        select(NodeORM)
        .where(NodeORM.graph_id == graph_id)
        .order_by(NodeORM.sort_order, NodeORM.created_at)
    ).all()


def read_intra_graph_edges(session: Session, graph_id: str) -> list[EdgeORM]:
    """读取两端都落在该 sub-graph 内的边。

    阶段 1 只处理 sub-graph 内部边；跨 sub-graph 的边在阶段 6 引入。
    """
    node_ids = {
        node_id
        for (node_id,) in session.execute(
            select(NodeORM.id).where(NodeORM.graph_id == graph_id)
        ).all()
    }
    if not node_ids:
        return []

    return session.scalars(
        select(EdgeORM)
        .where(EdgeORM.source.in_(node_ids), EdgeORM.target.in_(node_ids))
        .order_by(EdgeORM.sort_order, EdgeORM.created_at)
    ).all()


def read_graph_nodes(graph_id: str) -> list[NodeORM]:
    """在独立会话内读取 sub-graph 节点快照，供事务外对比索引 fingerprint。"""
    with SessionLocal() as session:
        return read_ordered_nodes_by_graph(session, graph_id)


def replace_subgraph(
    session: Session,
    graph: GraphORM,
    nodes: list[NodePayload],
    edges: list[EdgePayload],
) -> None:
    """整体替换某个 sub-graph 的节点与内部边。

    与 ``replace_graph`` 同构，但作用域收敛到单个 sub-graph：只删除/写入归属
    本 sub-graph 的节点和两端都在本 sub-graph 内的边，不影响项目下其他 sub-graph。
    """
    validate_edges_against_payload_nodes(nodes, edges)

    old_node_ids = {
        node_id
        for (node_id,) in session.execute(
            select(NodeORM.id).where(NodeORM.graph_id == graph.id)
        ).all()
    }
    # 先删内部边（外键约束阻止删除仍被边引用的节点），再删节点。
    if old_node_ids:
        session.query(EdgeORM).filter(
            EdgeORM.source.in_(old_node_ids), EdgeORM.target.in_(old_node_ids)
        ).delete(synchronize_session=False)
    session.query(NodeORM).filter(NodeORM.graph_id == graph.id).delete(
        synchronize_session=False
    )

    for index, node in enumerate(nodes):
        session.add(node_to_orm(graph.project_id, node, index, graph_id=graph.id))

    for index, edge in enumerate(edges):
        session.add(edge_to_orm(graph.project_id, edge, index))
