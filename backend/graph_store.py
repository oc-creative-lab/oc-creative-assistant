from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import SessionLocal
from models import EdgeORM, NodeORM, ProjectORM
from schemas import (
    EdgePayload,
    GraphPayload,
    NodePayload,
    PositionPayload,
    ProjectPayload,
    SaveGraphRequest,
    UpdateNodeRequest,
)


DEFAULT_PROJECT_ID = "default-project"
DEFAULT_PROJECT_NAME = "星庭档案"
META_TEXT_KEY = "text"


DEFAULT_NODES = [
    NodePayload(
        id="char-airin",
        type="character",
        title="艾琳",
        content="年轻的见习记录官，对王都隐藏的魔法痕迹异常敏感。",
        meta="主角 / 视角节点",
        typeLabel="角色",
        position=PositionPayload(x=40, y=80),
    ),
    NodePayload(
        id="char-mentor",
        type="character",
        title="导师",
        content="曾经服务于王室档案馆，保留着关于古老契约的秘密。",
        meta="引导者 / 信息源",
        typeLabel="角色",
        position=PositionPayload(x=40, y=290),
    ),
    NodePayload(
        id="world-capital",
        type="worldbuilding",
        title="王都",
        content="建在三层古城遗址上的都城，地下仍有未注销的旧魔法阵。",
        meta="核心场景 / 城市",
        typeLabel="世界观",
        position=PositionPayload(x=360, y=40),
    ),
    NodePayload(
        id="world-magic-rule",
        type="worldbuilding",
        title="魔法规则",
        content="所有术式都需要以真名或记忆作为锚点，代价会追溯到施术者。",
        meta="规则 / 约束",
        typeLabel="设定",
        position=PositionPayload(x=360, y=250),
    ),
    NodePayload(
        id="plot-first-meet",
        type="plot",
        title="初遇事件",
        content="艾琳在王都集市追查失窃档案，意外遇到伪装身份的导师。",
        meta="第一幕 / 开端",
        typeLabel="剧情",
        position=PositionPayload(x=700, y=120),
    ),
    NodePayload(
        id="plot-conflict-rise",
        type="plot",
        title="冲突升级",
        content="魔法阵被意外启动，王都地下遗址开始影响地表秩序。",
        meta="第二幕 / 压力",
        typeLabel="剧情",
        position=PositionPayload(x=1020, y=210),
    ),
]


DEFAULT_EDGES = [
    EdgePayload(id="edge-airin-first-meet", source="char-airin", target="plot-first-meet"),
    EdgePayload(id="edge-mentor-first-meet", source="char-mentor", target="plot-first-meet"),
    EdgePayload(id="edge-capital-first-meet", source="world-capital", target="plot-first-meet"),
    EdgePayload(id="edge-magic-conflict", source="world-magic-rule", target="plot-conflict-rise"),
    EdgePayload(
        id="edge-first-meet-conflict",
        source="plot-first-meet",
        target="plot-conflict-rise",
        animated=True,
    ),
]


def ensure_default_project() -> ProjectPayload:
    """确保默认项目存在；首次启动时写入项目和示例 graph。"""
    with SessionLocal.begin() as session:
        project = session.get(ProjectORM, DEFAULT_PROJECT_ID)

        if project is None:
            project = ProjectORM(id=DEFAULT_PROJECT_ID, name=DEFAULT_PROJECT_NAME)
            session.add(project)
            session.flush()
            _replace_graph(session, DEFAULT_PROJECT_ID, DEFAULT_NODES, DEFAULT_EDGES)
            return _project_to_payload(project)

        has_nodes = session.scalar(
            select(NodeORM.id).where(NodeORM.project_id == DEFAULT_PROJECT_ID).limit(1)
        )

        if has_nodes is None:
            _replace_graph(session, DEFAULT_PROJECT_ID, DEFAULT_NODES, DEFAULT_EDGES)

        return _project_to_payload(project)


def get_project(project_id: str) -> ProjectPayload:
    """读取项目基本信息；不存在时返回 404。"""
    with SessionLocal() as session:
        project = session.get(ProjectORM, project_id)

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        return _project_to_payload(project)


def get_project_graph(project_id: str) -> GraphPayload:
    """读取项目 graph，并转换为前端 DTO。"""
    with SessionLocal() as session:
        project = session.get(ProjectORM, project_id)

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        nodes = session.scalars(
            select(NodeORM)
            .where(NodeORM.project_id == project_id)
            .order_by(NodeORM.sort_order, NodeORM.created_at)
        ).all()
        edges = session.scalars(
            select(EdgeORM)
            .where(EdgeORM.project_id == project_id)
            .order_by(EdgeORM.sort_order, EdgeORM.created_at)
        ).all()

        return GraphPayload(
            project=_project_to_payload(project),
            nodes=[_node_to_payload(node) for node in nodes],
            edges=[_edge_to_payload(edge) for edge in edges],
        )


def save_project_graph(project_id: str, payload: SaveGraphRequest) -> GraphPayload:
    """手动保存策略：用前端当前 graph 快照整体替换项目 nodes / edges。"""
    with SessionLocal.begin() as session:
        project = session.get(ProjectORM, project_id)

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        _replace_graph(session, project_id, payload.nodes, payload.edges)

    return get_project_graph(project_id)


def create_node(project_id: str, node: NodePayload) -> NodePayload:
    """创建或覆盖单个节点，供后续细粒度保存复用。"""
    with SessionLocal.begin() as session:
        _require_project(session, project_id)
        session.merge(_node_to_orm(project_id, node, sort_order=0))

    return node


def update_node(project_id: str, node_id: str, payload: UpdateNodeRequest) -> NodePayload:
    """更新节点基础内容和位置；当前前端主要使用整体保存接口。"""
    with SessionLocal.begin() as session:
        _require_project(session, project_id)
        node = session.get(NodeORM, node_id)

        if node is None or node.project_id != project_id:
            raise HTTPException(status_code=404, detail="Node not found")

        if payload.title is not None:
            node.title = payload.title
        if payload.content is not None:
            node.content = payload.content
        if payload.meta is not None:
            node.meta = _api_meta_to_db(payload.meta)
        if payload.typeLabel is not None:
            node.type_label = payload.typeLabel
        if payload.position is not None:
            node.position_x = payload.position.x
            node.position_y = payload.position.y

        updated = _node_to_payload(node)

    return updated


def create_edge(project_id: str, edge: EdgePayload) -> EdgePayload:
    """创建或覆盖单条边，并校验两端节点属于同一项目。"""
    with SessionLocal.begin() as session:
        _require_project(session, project_id)
        _validate_edge_endpoints_in_project(session, project_id, edge.source, edge.target)
        session.merge(_edge_to_orm(project_id, edge, sort_order=0))

    return edge


def _replace_graph(
    session: Session,
    project_id: str,
    nodes: list[NodePayload],
    edges: list[EdgePayload],
) -> None:
    """在一个事务里替换 graph，避免节点和边只保存一半。"""
    _validate_edges_against_payload_nodes(nodes, edges)
    session.query(EdgeORM).filter(EdgeORM.project_id == project_id).delete(synchronize_session=False)
    session.query(NodeORM).filter(NodeORM.project_id == project_id).delete(synchronize_session=False)

    for index, node in enumerate(nodes):
        session.add(_node_to_orm(project_id, node, index))

    for index, edge in enumerate(edges):
        session.add(_edge_to_orm(project_id, edge, index))


def _require_project(session: Session, project_id: str) -> ProjectORM:
    """复用项目存在性校验，避免各 API 分支重复写 404 逻辑。"""
    project = session.get(ProjectORM, project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


def _validate_edges_against_payload_nodes(nodes: list[NodePayload], edges: list[EdgePayload]) -> None:
    """保存整张图时，业务层保证 edge 两端都在同一批项目节点里。"""
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


def _validate_edge_endpoints_in_project(
    session: Session,
    project_id: str,
    source: str,
    target: str,
) -> None:
    """单独创建 edge 时，业务层保证 source/target 都属于当前 project。"""
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


def _project_to_payload(project: ProjectORM) -> ProjectPayload:
    """ORM project -> API payload。"""
    return ProjectPayload(id=project.id, name=project.name)


def _node_to_payload(node: NodeORM) -> NodePayload:
    """ORM node -> API payload，meta JSON 兼容当前前端的字符串 meta。"""
    return NodePayload(
        id=node.id,
        type=node.node_type,
        title=node.title,
        content=node.content,
        meta=_db_meta_to_api(node.meta),
        typeLabel=node.type_label,
        position=PositionPayload(x=node.position_x, y=node.position_y),
    )


def _edge_to_payload(edge: EdgeORM) -> EdgePayload:
    """ORM edge -> API payload，保留 Vue Flow handle 信息。"""
    return EdgePayload(
        id=edge.id,
        source=edge.source,
        target=edge.target,
        label=edge.label,
        sourceHandle=edge.source_handle,
        targetHandle=edge.target_handle,
        type=edge.edge_type,
        animated=edge.animated,
    )


def _node_to_orm(project_id: str, node: NodePayload, sort_order: int) -> NodeORM:
    """API payload -> ORM node，用于新增、覆盖和批量保存。"""
    return NodeORM(
        id=node.id,
        project_id=project_id,
        node_type=node.type,
        title=node.title,
        content=node.content,
        meta=_api_meta_to_db(node.meta),
        type_label=node.typeLabel,
        position_x=node.position.x,
        position_y=node.position.y,
        sort_order=sort_order,
    )


def _edge_to_orm(project_id: str, edge: EdgePayload, sort_order: int) -> EdgeORM:
    """API payload -> ORM edge，用于新增、覆盖和批量保存。"""
    return EdgeORM(
        id=edge.id,
        project_id=project_id,
        source=edge.source,
        target=edge.target,
        label=edge.label,
        source_handle=edge.sourceHandle,
        target_handle=edge.targetHandle,
        edge_type=edge.type,
        animated=edge.animated,
        sort_order=sort_order,
    )


def _api_meta_to_db(meta: str) -> dict[str, str]:
    """当前 API 仍接收字符串 meta，数据库层用 JSON 包装，后续可扩展更多字段。"""
    return {META_TEXT_KEY: meta} if meta else {}


def _db_meta_to_api(meta: Any) -> str:
    """兼容旧库中可能存在的字符串 meta，同时支持新的 JSON 对象。"""
    if isinstance(meta, dict):
        value = meta.get(META_TEXT_KEY, "")
        return value if isinstance(value, str) else ""

    if isinstance(meta, str):
        return meta

    return ""
