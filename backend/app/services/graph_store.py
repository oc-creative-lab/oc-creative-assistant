"""Graph 应用服务。

本模块属于服务层编排入口，负责维护项目 graph 的事务边界，并在 SQLite
提交后同步可重建的向量索引。它不直接处理 HTTP 请求，也不决定 RAG prompt
或检索策略。
"""

from fastapi import HTTPException

from app.db.database import SessionLocal
from app.db.models import NodeORM, ProjectORM
from app.indexing.sync import (
    build_node_fingerprint,
    safe_sync_node_index,
    safe_sync_project_index_incremental,
)
from app.schemas import (
    EdgePayload,
    GraphPayload,
    NodePayload,
    ProjectPayload,
    SaveGraphRequest,
    UpdateNodeRequest,
)
from app.services.graph_mappers import (
    api_meta_to_db,
    db_meta_to_api,
    db_status_to_api,
    db_tags_to_api,
    edge_to_orm,
    edge_to_payload,
    node_to_orm,
    node_to_payload,
    project_to_payload,
)
from app.services.graph_repository import (
    read_ordered_edges,
    read_ordered_nodes,
    read_project_node,
    read_project_nodes,
    replace_graph,
    require_project,
)
from app.services.graph_seed import (
    DEFAULT_EDGES,
    DEFAULT_NODES,
    DEFAULT_PROJECT_ID,
    DEFAULT_PROJECT_NAME,
)
from app.services.graph_validation import validate_edge_endpoints_in_project


def ensure_default_project() -> ProjectPayload:
    """确保默认项目存在。

    首次启动时会写入默认项目和示例 graph；如果只存在项目记录但没有节点，
    也会补写示例 graph，修复半初始化状态。

    Returns:
        默认项目 DTO。
    """
    with SessionLocal.begin() as session:
        project = session.get(ProjectORM, DEFAULT_PROJECT_ID)

        if project is None:
            project = ProjectORM(id=DEFAULT_PROJECT_ID, name=DEFAULT_PROJECT_NAME)
            session.add(project)
            session.flush()
            replace_graph(session, DEFAULT_PROJECT_ID, DEFAULT_NODES, DEFAULT_EDGES)
            return project_to_payload(project)

        has_nodes = read_ordered_nodes(session, DEFAULT_PROJECT_ID)

        if not has_nodes:
            replace_graph(session, DEFAULT_PROJECT_ID, DEFAULT_NODES, DEFAULT_EDGES)

        return project_to_payload(project)


def get_project(project_id: str) -> ProjectPayload:
    """读取项目基本信息。

    Args:
        project_id: 项目 ID。

    Returns:
        项目 DTO。

    Raises:
        HTTPException: 当项目不存在时抛出 404。
    """
    with SessionLocal() as session:
        return project_to_payload(require_project(session, project_id))


def get_project_graph(project_id: str) -> GraphPayload:
    """读取项目 graph，并转换为前端 DTO。

    Args:
        project_id: 项目 ID。

    Returns:
        项目、节点和边的完整快照。

    Raises:
        HTTPException: 当项目不存在时抛出 404。
    """
    with SessionLocal() as session:
        project = require_project(session, project_id)
        nodes = read_ordered_nodes(session, project_id)
        edges = read_ordered_edges(session, project_id)

        return GraphPayload(
            project=project_to_payload(project),
            nodes=[node_to_payload(node) for node in nodes],
            edges=[edge_to_payload(edge) for edge in edges],
        )


def save_project_graph(project_id: str, payload: SaveGraphRequest) -> GraphPayload:
    """整体替换项目 graph，并在事务提交后增量同步向量索引。

    Args:
        project_id: 项目 ID。
        payload: 前端当前完整 nodes/edges 快照。

    Returns:
        数据库最终保存后的 graph 快照。

    Raises:
        HTTPException: 当项目不存在或边引用非法节点时抛出。
    """
    old_nodes = read_project_nodes(project_id)

    with SessionLocal.begin() as session:
        require_project(session, project_id)
        replace_graph(session, project_id, payload.nodes, payload.edges)

    # ChromaDB 依赖已提交的 SQLite 状态，因此必须在事务完成后按 fingerprint 增量同步。
    new_nodes = read_project_nodes(project_id)
    safe_sync_project_index_incremental(project_id, old_nodes, new_nodes)

    return get_project_graph(project_id)


def create_node(project_id: str, node: NodePayload) -> NodePayload:
    """创建或覆盖单个节点，并在提交后同步向量索引。

    Args:
        project_id: 节点所属项目 ID。
        node: 前端提交的节点 DTO。

    Returns:
        已保存的节点 DTO。

    Raises:
        HTTPException: 当项目不存在时抛出。
    """
    with SessionLocal.begin() as session:
        require_project(session, project_id)
        session.merge(node_to_orm(project_id, node, sort_order=0))

    latest_node = read_project_node(project_id, node.id)

    if latest_node is not None:
        safe_sync_node_index(latest_node)

    return node


def update_node(project_id: str, node_id: str, payload: UpdateNodeRequest) -> NodePayload:
    """更新节点基础内容或位置，并在检索文档变化时同步向量索引。

    Args:
        project_id: 节点所属项目 ID。
        node_id: 需要更新的节点 ID。
        payload: 局部更新字段；字段为 None 表示不修改。

    Returns:
        更新后的节点 DTO。

    Raises:
        HTTPException: 当项目或节点不存在时抛出。
    """
    with SessionLocal.begin() as session:
        require_project(session, project_id)
        node = session.get(NodeORM, node_id)

        if node is None or node.project_id != project_id:
            raise HTTPException(status_code=404, detail="Node not found")

        old_fingerprint = build_node_fingerprint(node)

        if payload.title is not None:
            node.title = payload.title
        if payload.content is not None:
            node.content = payload.content
        if payload.meta is not None:
            node.meta = api_meta_to_db(
                payload.meta,
                payload.tags,
                payload.status,
                existing_meta=node.meta,
            )
        if payload.typeLabel is not None:
            node.type_label = payload.typeLabel
        if payload.nodeType is not None:
            node.node_type = payload.nodeType
        if payload.tags is not None:
            node.meta = api_meta_to_db(
                db_meta_to_api(node.meta),
                payload.tags,
                db_status_to_api(node.meta),
            )
        if payload.status is not None:
            node.meta = api_meta_to_db(
                db_meta_to_api(node.meta),
                db_tags_to_api(node.meta),
                payload.status,
            )
        if payload.position is not None:
            node.position_x = payload.position.x
            node.position_y = payload.position.y

        updated = node_to_payload(node)

    # 索引同步必须使用已提交状态，避免 ChromaDB 与 SQLite 在失败回滚时出现分叉。
    latest_node = read_project_node(project_id, node_id)
    if latest_node is not None:
        safe_sync_node_index(latest_node, old_fingerprint)

    return updated


def create_edge(project_id: str, edge: EdgePayload) -> EdgePayload:
    """创建或覆盖单条边，并校验两端节点属于同一项目。

    Args:
        project_id: 边所属项目 ID。
        edge: 前端提交的边 DTO。

    Returns:
        已保存的边 DTO。

    Raises:
        HTTPException: 当项目不存在或边端点不属于同一项目时抛出。
    """
    with SessionLocal.begin() as session:
        require_project(session, project_id)
        validate_edge_endpoints_in_project(session, project_id, edge.source, edge.target)
        session.merge(edge_to_orm(project_id, edge, sort_order=0))

    return edge
