"""Graph DTO 与 ORM 转换。

本模块属于服务层的数据映射边界，负责在 API payload 与 SQLAlchemy ORM
之间转换，并维护 node meta JSON 的兼容规则。它不访问数据库，也不触发索引同步。
"""

from __future__ import annotations

from typing import Any

from app.db.models import EdgeORM, NodeORM, ProjectORM
from app.indexing.config import DEFAULT_NODE_STATUS
from app.schemas import EdgePayload, NodePayload, PositionPayload, ProjectPayload


META_TEXT_KEY = "text"
META_TAGS_KEY = "tags"
META_STATUS_KEY = "status"


def project_to_payload(project: ProjectORM) -> ProjectPayload:
    """将项目 ORM 转换为 API payload。

    Args:
        project: 数据库中的项目记录。

    Returns:
        前端接口使用的项目 DTO。
    """
    return ProjectPayload(id=project.id, name=project.name)


def node_to_payload(node: NodeORM) -> NodePayload:
    """将节点 ORM 转换为 API payload。

    该函数兼容历史字符串 meta 与当前 JSON meta，保证前端仍收到稳定的
    `meta`、`tags`、`status` 字段。

    Args:
        node: 数据库中的节点记录。

    Returns:
        前端接口使用的节点 DTO。
    """
    return NodePayload(
        id=node.id,
        type=node.node_type,
        nodeType=node.node_type,
        title=node.title,
        content=node.content,
        meta=db_meta_to_api(node.meta),
        typeLabel=node.type_label,
        tags=db_tags_to_api(node.meta),
        status=db_status_to_api(node.meta),
        position=PositionPayload(x=node.position_x, y=node.position_y),
    )


def edge_to_payload(edge: EdgeORM) -> EdgePayload:
    """将边 ORM 转换为 API payload。

    Args:
        edge: 数据库中的边记录。

    Returns:
        保留 Vue Flow handle 和样式信息的边 DTO。
    """
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


def node_to_orm(project_id: str, node: NodePayload, sort_order: int) -> NodeORM:
    """将节点 payload 转换为 ORM。

    Args:
        project_id: 节点所属项目 ID。
        node: 前端提交的节点 DTO。
        sort_order: 节点在当前 graph 快照中的顺序。

    Returns:
        可写入数据库的节点 ORM 对象。
    """
    return NodeORM(
        id=node.id,
        project_id=project_id,
        node_type=node.nodeType or node.type,
        title=node.title,
        content=node.content,
        meta=api_meta_to_db(node.meta, node.tags, node.status),
        type_label=node.typeLabel,
        position_x=node.position.x,
        position_y=node.position.y,
        sort_order=sort_order,
    )


def edge_to_orm(project_id: str, edge: EdgePayload, sort_order: int) -> EdgeORM:
    """将边 payload 转换为 ORM。

    Args:
        project_id: 边所属项目 ID。
        edge: 前端提交的边 DTO。
        sort_order: 边在当前 graph 快照中的顺序。

    Returns:
        可写入数据库的边 ORM 对象。
    """
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


def api_meta_to_db(
    meta: str,
    tags: list[str] | None = None,
    status: str | None = None,
    existing_meta: Any | None = None,
) -> dict[str, Any]:
    """将 API meta 字段合并为数据库 JSON。

    API 仍保留字符串 `meta` 字段；数据库用 JSON 同时保存正文、标签和同步状态，
    避免在当前 PoC 阶段扩展表结构。

    Args:
        meta: 前端提交的字符串 meta。
        tags: 可选标签列表；为 None 时保留已有标签或写入默认空列表。
        status: 可选同步状态；为 None 时保留已有状态或写入默认状态。
        existing_meta: 更新节点时已有的数据库 meta。

    Returns:
        可写入 NodeORM.meta 的 JSON 字典。
    """
    stored_meta: dict[str, Any] = existing_meta if isinstance(existing_meta, dict) else {}
    next_meta = dict(stored_meta)

    if meta:
        next_meta[META_TEXT_KEY] = meta
    else:
        next_meta.pop(META_TEXT_KEY, None)

    if tags is not None:
        next_meta[META_TAGS_KEY] = [tag for tag in tags if isinstance(tag, str)]
    elif META_TAGS_KEY not in next_meta:
        next_meta[META_TAGS_KEY] = []

    if status is not None:
        next_meta[META_STATUS_KEY] = status
    elif META_STATUS_KEY not in next_meta:
        next_meta[META_STATUS_KEY] = DEFAULT_NODE_STATUS

    return next_meta


def db_meta_to_api(meta: Any) -> str:
    """从数据库 meta 读取 API 字符串 meta。"""
    if isinstance(meta, dict):
        value = meta.get(META_TEXT_KEY, "")
        return value if isinstance(value, str) else ""

    if isinstance(meta, str):
        return meta

    return ""


def db_tags_to_api(meta: Any) -> list[str]:
    """从数据库 meta 读取 API tags。"""
    if isinstance(meta, dict):
        tags = meta.get(META_TAGS_KEY, [])
        return [tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else []

    return []


def db_status_to_api(meta: Any) -> str:
    """从数据库 meta 读取 API status。"""
    if isinstance(meta, dict):
        status = meta.get(META_STATUS_KEY, DEFAULT_NODE_STATUS)
        return status if isinstance(status, str) else DEFAULT_NODE_STATUS

    return DEFAULT_NODE_STATUS
