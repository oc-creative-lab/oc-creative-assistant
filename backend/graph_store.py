from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import SessionLocal
from models import EdgeORM, NodeORM, ProjectORM
from rag.index_sync import (
    build_node_fingerprint,
    safe_sync_node_index,
    safe_sync_project_index_incremental,
)
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
META_TAGS_KEY = "tags"
META_STATUS_KEY = "status"
DEFAULT_NODE_STATUS = "draft"


# 首次启动时写入的示例节点，保证前端在没有用户数据时也能展示完整画布流程。
DEFAULT_NODES = [
    NodePayload(
        id="char-airin",
        type="character",
        title="艾琳",
        content="年轻的见习记录官，对王都隐藏的魔法痕迹异常敏感。",
        meta="主角 / 视角节点",
        typeLabel="角色",
        tags=["角色", "主角"],
        status="synced",
        position=PositionPayload(x=40, y=80),
    ),
    NodePayload(
        id="char-mentor",
        type="character",
        title="导师",
        content="曾经服务于王室档案馆，保留着关于古老契约的秘密。",
        meta="引导者 / 信息源",
        typeLabel="角色",
        tags=["角色", "导师"],
        status="draft",
        position=PositionPayload(x=40, y=290),
    ),
    NodePayload(
        id="world-capital",
        type="worldbuilding",
        title="王都",
        content="建在三层古城遗址上的都城，地下仍有未注销的旧魔法阵。",
        meta="核心场景 / 城市",
        typeLabel="世界观",
        tags=["世界观", "城市"],
        status="synced",
        position=PositionPayload(x=360, y=40),
    ),
    NodePayload(
        id="world-magic-rule",
        type="worldbuilding",
        title="魔法规则",
        content="所有术式都需要以真名或记忆作为锚点，代价会追溯到施术者。",
        meta="规则 / 约束",
        typeLabel="设定",
        tags=["世界观", "规则"],
        status="outdated",
        position=PositionPayload(x=360, y=250),
    ),
    NodePayload(
        id="plot-first-meet",
        type="plot",
        title="初遇事件",
        content="艾琳在王都集市追查失窃档案，意外遇到伪装身份的导师。",
        meta="第一幕 / 开端",
        typeLabel="剧情",
        tags=["剧情", "第一幕"],
        status="draft",
        position=PositionPayload(x=700, y=120),
    ),
    NodePayload(
        id="plot-conflict-rise",
        type="plot",
        title="冲突升级",
        content="魔法阵被意外启动，王都地下遗址开始影响地表秩序。",
        meta="第二幕 / 压力",
        typeLabel="剧情",
        tags=["剧情", "冲突"],
        status="draft",
        position=PositionPayload(x=1020, y=210),
    ),
    NodePayload(
        id="idea-memory-cost",
        type="idea",
        title="记忆代价灵感",
        content="如果真名魔法会改写记忆，角色每次施术都可能遗失一个重要关系。",
        meta="灵感 / 代价",
        typeLabel="灵感",
        tags=["灵感", "魔法"],
        status="draft",
        position=PositionPayload(x=700, y=340),
    ),
    NodePayload(
        id="research-archive-source",
        type="research",
        title="档案馆资料来源",
        content="记录王室档案馆公开职责、隐藏职责和旧契约材料的参考摘要。",
        meta="资料 / 档案",
        typeLabel="资料",
        tags=["资料", "档案"],
        status="draft",
        position=PositionPayload(x=1020, y=20),
    ),
    NodePayload(
        id="structure-act-one",
        type="structure",
        title="第一幕结构整理",
        content="把失窃档案、初遇导师、魔法阵异动串成第一幕的因果链。",
        meta="结构 / 第一幕",
        typeLabel="结构整理",
        tags=["结构", "剧情"],
        status="draft",
        position=PositionPayload(x=1320, y=180),
    ),
]


# 示例边刻意覆盖角色、世界观、剧情之间的连接，用来验证保存/恢复连线信息。
DEFAULT_EDGES = [
    EdgePayload(
        id="edge-airin-first-meet",
        source="char-airin",
        target="plot-first-meet",
        label="参与",
        relationType="belongs_to",
    ),
    EdgePayload(
        id="edge-mentor-first-meet",
        source="char-mentor",
        target="plot-first-meet",
        label="推动",
        relationType="causes",
    ),
    EdgePayload(
        id="edge-capital-first-meet",
        source="world-capital",
        target="plot-first-meet",
        label="发生于",
        relationType="belongs_to",
    ),
    EdgePayload(
        id="edge-magic-conflict",
        source="world-magic-rule",
        target="plot-conflict-rise",
        label="导致",
        relationType="causes",
    ),
    EdgePayload(
        id="edge-first-meet-conflict",
        source="plot-first-meet",
        target="plot-conflict-rise",
        label="发展为",
        relationType="develops_into",
        animated=True,
    ),
    EdgePayload(
        id="edge-idea-magic-rule",
        source="idea-memory-cost",
        target="world-magic-rule",
        label="补充",
        relationType="references",
    ),
    EdgePayload(
        id="edge-conflict-structure",
        source="plot-conflict-rise",
        target="structure-act-one",
        label="整理为",
        relationType="develops_into",
    ),
]


def ensure_default_project() -> ProjectPayload:
    """确保默认项目存在；首次启动时写入项目和示例 graph。"""
    # 入参：无。返回：默认项目 DTO。状态影响：可能创建项目、节点和边。
    with SessionLocal.begin() as session:
        project = session.get(ProjectORM, DEFAULT_PROJECT_ID)

        if project is None:
            # 新建项目后先 flush，确保后续节点/边的外键能在同一事务中引用项目。
            project = ProjectORM(id=DEFAULT_PROJECT_ID, name=DEFAULT_PROJECT_NAME)
            session.add(project)
            session.flush()
            _replace_graph(session, DEFAULT_PROJECT_ID, DEFAULT_NODES, DEFAULT_EDGES)
            return _project_to_payload(project)

        has_nodes = session.scalar(
            select(NodeORM.id).where(NodeORM.project_id == DEFAULT_PROJECT_ID).limit(1)
        )

        if has_nodes is None:
            # 兼容只有项目记录、没有 graph 数据的半初始化状态。
            _replace_graph(session, DEFAULT_PROJECT_ID, DEFAULT_NODES, DEFAULT_EDGES)

        return _project_to_payload(project)


def get_project(project_id: str) -> ProjectPayload:
    """读取项目基本信息；不存在时返回 404。"""
    # 入参 project_id 是路径中的项目 id；该函数只读数据库，不修改状态。
    with SessionLocal() as session:
        project = session.get(ProjectORM, project_id)

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        return _project_to_payload(project)


def get_project_graph(project_id: str) -> GraphPayload:
    """读取项目 graph，并转换为前端 DTO。"""
    # 入参 project_id 定位项目；返回项目、节点和边的完整快照。
    # 只读数据库；排序使用 sort_order + created_at 保证前端每次恢复顺序稳定。
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


def _read_project_nodes(project_id: str) -> list[NodeORM]:
    """读取项目节点快照，供 Chroma 同步在 SQLite 事务外做 fingerprint 对比。"""
    with SessionLocal() as session:
        return session.scalars(
            select(NodeORM)
            .where(NodeORM.project_id == project_id)
            .order_by(NodeORM.sort_order, NodeORM.created_at)
        ).all()


def _read_project_node(project_id: str, node_id: str) -> NodeORM | None:
    """提交后重新读取单节点，确保同步 Chroma 使用的是 SQLite 已落库的最新数据。"""
    with SessionLocal() as session:
        node = session.get(NodeORM, node_id)

        if node is None or node.project_id != project_id:
            return None

        return node


def save_project_graph(project_id: str, payload: SaveGraphRequest) -> GraphPayload:
    """手动保存策略：用前端当前 graph 快照整体替换项目 nodes / edges。"""
    # 入参 payload.nodes/payload.edges 来自 Vue Flow 当前画布状态。
    # 状态影响：会删除该项目原有节点和边，再写入新的完整快照。
    old_nodes = _read_project_nodes(project_id)

    with SessionLocal.begin() as session:
        project = session.get(ProjectORM, project_id)

        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        _replace_graph(session, project_id, payload.nodes, payload.edges)

    new_nodes = _read_project_nodes(project_id)
    # 整图保存会重建 SQLite 行；这里只按检索文档 fingerprint 增量同步，避免拖动节点也重算 embedding。
    safe_sync_project_index_incremental(project_id, old_nodes, new_nodes)

    # 重新读取一次，确保响应使用数据库最终排序和 ORM -> DTO 转换结果。
    return get_project_graph(project_id)


def create_node(project_id: str, node: NodePayload) -> NodePayload:
    """创建或覆盖单个节点，供后续细粒度保存复用。"""
    # 入参 node 是单个前端节点 DTO；状态影响：merge 会插入或覆盖同 id 节点。
    with SessionLocal.begin() as session:
        _require_project(session, project_id)
        session.merge(_node_to_orm(project_id, node, sort_order=0))

    latest_node = _read_project_node(project_id, node.id)

    if latest_node is not None:
        safe_sync_node_index(latest_node)

    return node


def update_node(project_id: str, node_id: str, payload: UpdateNodeRequest) -> NodePayload:
    """更新节点基础内容和位置；当前前端主要使用整体保存接口。"""
    # 入参 payload 是 PATCH 语义：字段为 None 表示保留数据库原值。
    # 状态影响：只修改当前项目内指定节点，返回转换后的最新 DTO。
    with SessionLocal.begin() as session:
        _require_project(session, project_id)
        node = session.get(NodeORM, node_id)

        if node is None or node.project_id != project_id:
            raise HTTPException(status_code=404, detail="Node not found")

        old_fingerprint = build_node_fingerprint(node)

        # PATCH 语义：只有显式传入的字段才覆盖数据库，空字符串仍是合法更新值。
        if payload.title is not None:
            node.title = payload.title
        if payload.content is not None:
            node.content = payload.content
        if payload.meta is not None:
            # meta 更新时同时接收 tags/status，避免前端一次提交拆成多次数据库写入。
            node.meta = _api_meta_to_db(
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
            # 单独更新 tags 时保留已有 meta 文本和 status，防止局部 PATCH 丢失其它 meta 信息。
            node.meta = _api_meta_to_db(
                _db_meta_to_api(node.meta),
                payload.tags,
                _db_status_to_api(node.meta),
            )
        if payload.status is not None:
            # 单独更新 status 时保留已有 meta 文本和 tags。
            node.meta = _api_meta_to_db(
                _db_meta_to_api(node.meta),
                _db_tags_to_api(node.meta),
                payload.status,
            )
        if payload.position is not None:
            node.position_x = payload.position.x
            node.position_y = payload.position.y

        updated = _node_to_payload(node)

    latest_node = _read_project_node(project_id, node_id)

    if latest_node is not None:
        safe_sync_node_index(latest_node, old_fingerprint)

    return updated


def create_edge(project_id: str, edge: EdgePayload) -> EdgePayload:
    """创建或覆盖单条边，并校验两端节点属于同一项目。"""
    # 入参 edge 是 Vue Flow 边 DTO；source/target 必须指向当前项目内节点。
    # 状态影响：merge 会插入或覆盖同 id 边，包含 handle 和关系类型。
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
    # 入参 nodes/edges 是同一次前端保存的完整快照；函数不返回值。
    # 状态影响：该项目 graph 被整体替换，因此必须先校验边端点都在本批 nodes 中。
    _validate_edges_against_payload_nodes(nodes, edges)
    # 先删边再删节点，避免 SQLite 外键约束在替换过程中阻止删除节点。
    session.query(EdgeORM).filter(EdgeORM.project_id == project_id).delete(synchronize_session=False)
    session.query(NodeORM).filter(NodeORM.project_id == project_id).delete(synchronize_session=False)

    for index, node in enumerate(nodes):
        # sort_order 记录前端快照顺序，供后续读取时稳定还原。
        session.add(_node_to_orm(project_id, node, index))

    for index, edge in enumerate(edges):
        # 边必须在节点之后写入，否则外键约束无法确认 source/target 已存在。
        session.add(_edge_to_orm(project_id, edge, index))


def _require_project(session: Session, project_id: str) -> ProjectORM:
    """复用项目存在性校验，避免各 API 分支重复写 404 逻辑。"""
    # 返回 ORM 项目对象；只读数据库，不修改状态。
    project = session.get(ProjectORM, project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


def _validate_edges_against_payload_nodes(nodes: list[NodePayload], edges: list[EdgePayload]) -> None:
    """保存整张图时，业务层保证 edge 两端都在同一批项目节点里。"""
    # 用集合做 O(1) 端点查找，避免大画布保存时反复扫描节点列表。
    node_ids = {node.id for node in nodes}
    # 这里仅校验端点存在性；重复边/自环当前主要由前端交互层避免。
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
    # 这里校验“同项目”而不只校验“节点存在”，防止跨项目连线污染 graph。
    # 使用 count 而不是逐个 get，减少分支并避免接受跨项目节点。
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
    # Project DTO 只暴露前端当前需要的标识和展示名。
    return ProjectPayload(id=project.id, name=project.name)


def _node_to_payload(node: NodeORM) -> NodePayload:
    """ORM node -> API payload，meta JSON 兼容当前前端的字符串 meta。"""
    # position_x/position_y 在响应中重新合并为 Vue Flow 使用的 position 对象。
    # node_type 同时填充 type 和 nodeType，兼容画布渲染与详情编辑两处读取方式。
    return NodePayload(
        id=node.id,
        type=node.node_type,
        nodeType=node.node_type,
        title=node.title,
        content=node.content,
        meta=_db_meta_to_api(node.meta),
        typeLabel=node.type_label,
        tags=_db_tags_to_api(node.meta),
        status=_db_status_to_api(node.meta),
        position=PositionPayload(x=node.position_x, y=node.position_y),
    )


def _edge_to_payload(edge: EdgeORM) -> EdgePayload:
    """ORM edge -> API payload，保留 Vue Flow handle 信息。"""
    # source/target/sourceHandle/targetHandle 原样返回，确保前端能恢复连线端点和连接桩。
    return EdgePayload(
        id=edge.id,
        source=edge.source,
        target=edge.target,
        label=edge.label or "关联",
        relationType=edge.relation_type or "relates_to",
        sourceHandle=edge.source_handle,
        targetHandle=edge.target_handle,
        type=edge.edge_type,
        animated=edge.animated,
    )


def _node_to_orm(project_id: str, node: NodePayload, sort_order: int) -> NodeORM:
    """API payload -> ORM node，用于新增、覆盖和批量保存。"""
    # 前端 position 对象拆成两列，便于后续按坐标查询或迁移到其它 graph 存储。
    return NodeORM(
        id=node.id,
        project_id=project_id,
        node_type=node.nodeType or node.type,
        title=node.title,
        content=node.content,
        meta=_api_meta_to_db(node.meta, node.tags, node.status),
        type_label=node.typeLabel,
        position_x=node.position.x,
        position_y=node.position.y,
        sort_order=sort_order,
    )


def _edge_to_orm(project_id: str, edge: EdgePayload, sort_order: int) -> EdgeORM:
    """API payload -> ORM edge，用于新增、覆盖和批量保存。"""
    # source_handle/target_handle 允许为空，因为 Vue Flow 并不要求所有边都绑定具体 handle。
    return EdgeORM(
        id=edge.id,
        project_id=project_id,
        source=edge.source,
        target=edge.target,
        label=edge.label or "关联",
        source_handle=edge.sourceHandle,
        target_handle=edge.targetHandle,
        edge_type=edge.type,
        relation_type=edge.relationType,
        animated=edge.animated,
        sort_order=sort_order,
    )


def _api_meta_to_db(
    meta: str,
    tags: list[str] | None = None,
    status: str | None = None,
    existing_meta: Any | None = None,
) -> dict[str, Any]:
    """API 仍兼容字符串 meta，同时把 tags/status 放进 JSON，避免 PoC 阶段扩表。"""
    # existing_meta 用于 PATCH 局部更新：先复制已有 JSON，再覆盖本次明确传入的字段。
    stored_meta: dict[str, Any] = existing_meta if isinstance(existing_meta, dict) else {}
    next_meta = dict(stored_meta)

    if meta:
        next_meta[META_TEXT_KEY] = meta
    else:
        next_meta.pop(META_TEXT_KEY, None)

    if tags is not None:
        # 过滤非字符串值，避免脏数据进入 JSON 后影响前端标签渲染。
        next_meta[META_TAGS_KEY] = [tag for tag in tags if isinstance(tag, str)]
    elif META_TAGS_KEY not in next_meta:
        next_meta[META_TAGS_KEY] = []

    if status is not None:
        next_meta[META_STATUS_KEY] = status
    elif META_STATUS_KEY not in next_meta:
        next_meta[META_STATUS_KEY] = DEFAULT_NODE_STATUS

    return next_meta


def _db_meta_to_api(meta: Any) -> str:
    """兼容旧库中可能存在的字符串 meta，同时支持新的 JSON 对象。"""
    if isinstance(meta, dict):
        value = meta.get(META_TEXT_KEY, "")
        return value if isinstance(value, str) else ""

    if isinstance(meta, str):
        return meta

    return ""


def _db_tags_to_api(meta: Any) -> list[str]:
    """从 JSON meta 中读取 tags；旧数据没有 tags 时返回空列表。"""
    if isinstance(meta, dict):
        tags = meta.get(META_TAGS_KEY, [])
        # 读取时再次过滤，兼容旧库或手工编辑数据库产生的异常 JSON。
        return [tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else []

    return []


def _db_status_to_api(meta: Any) -> str:
    """从 JSON meta 中读取 status；旧数据默认视为 draft。"""
    if isinstance(meta, dict):
        status = meta.get(META_STATUS_KEY, DEFAULT_NODE_STATUS)
        return status if isinstance(status, str) else DEFAULT_NODE_STATUS

    return DEFAULT_NODE_STATUS
