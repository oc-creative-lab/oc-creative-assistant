"""把已结案的 staging 落到画布。

调用方负责把 staging 状态推到 ``accepted`` / ``edited``; 本模块只负责把
payload 翻译成 NodeORM/EdgeORM, 在同一事务内 flush 到 SQLite。

支持的变更类型:
- ``create_node``: 写 NodeORM, 标记 AI 来源, 同 batch 内的 pending_id 在
  返回时由调用方累积进 ``pending_id_map``; 同时把生成的 node_id 回写到
  ``record.target_id``, 让跨 HTTP 请求的单条接受 create_edge 也能从 DB 反查
- ``create_edge``: 写 EdgeORM; source / target 既可以是真实 node_id, 也可以
  是同 batch 内 create_node 的 pending_id; 端点失效或 LLM 编造时静默跳过,
  避免触发 SQLite 外键约束炸事务

ChromaDB 同步必须在事务提交后做, 因此本模块只返回新写入的 node_id, 由
调用方在事务关闭后逐一触发 ``safe_sync_node_index``。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.database import _SECTION_BY_NODE_TYPE, _DEFAULT_SECTION
from app.db.models import AgentStagingORM, EdgeORM, NodeORM, ProjectORM

logger = logging.getLogger(__name__)


_ACCEPTED_STATUSES = {"accepted", "edited"}

# section → ProjectORM 上对应的 graph_id 字段名。
_GRAPH_ID_ATTR_BY_SECTION = {
    "plot": "plot_graph_id",
    "character": "character_graph_id",
    "world": "world_graph_id",
}


def _resolve_graph_id(db: Session, project_id: str, node_type: str) -> str | None:
    """按 node_type 找出该节点应归属的 sub-graph id（first_revision 决策 1）。

    项目尚未迁移出 sub-graph（理论上不会发生）时返回 None，节点退化为无 graph_id。
    """
    project = db.get(ProjectORM, project_id)
    if project is None:
        return None
    section = _SECTION_BY_NODE_TYPE.get(node_type, _DEFAULT_SECTION)
    return getattr(project, _GRAPH_ID_ATTR_BY_SECTION[section], None)


def apply_staging_record(
    db: Session,
    record: AgentStagingORM,
    pending_id_map: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    """把单条 staging 落到画布。

    Returns:
        (upserted_node_id, deleted_node_id) 两元组:
        - upserted_node_id: create_node / update_node 落库后的真实 id, 调用方
          用于在事务关闭后触发 ChromaDB 重新嵌入;
        - deleted_node_id: delete_node 命中的真实 id, 调用方用于在事务关闭后
          把对应向量从 ChromaDB 移除, 避免残留。
        其它 change_type 一律返回 (None, None)。
    """
    if record.status not in _ACCEPTED_STATUSES:
        return None, None

    payload = record.payload_edited or record.payload

    if record.change_type == "create_node":
        new_id = _apply_create_node(db, record, payload)
        if pending_id_map is not None and record.pending_id:
            pending_id_map[record.pending_id] = new_id
        return new_id, None

    if record.change_type == "create_edge":
        _apply_create_edge(db, record, payload, pending_id_map or {})
        return None, None

    if record.change_type == "update_node":
        return _apply_update_node(db, record, payload), None

    if record.change_type == "delete_node":
        return None, _apply_delete_node(db, record)

    if record.change_type == "delete_edge":
        _apply_delete_edge(db, record, payload)
        return None, None

    return None, None


def _apply_create_node(db: Session, record: AgentStagingORM, payload: dict[str, Any]) -> str:
    """把 staging.payload 翻译成新节点。

    把生成的 node_id 回写到 record.target_id, 让后续"单条接受 create_edge"
    能从 DB 反查 pending_id → 真实 node_id (跨 HTTP 请求复用映射)。
    target_id 在 create_node 语义里本来就是空的, 复用这个字段不破坏语义。
    """
    node_id = uuid.uuid4().hex

    title = str(payload.get("title") or "AI 建议节点")
    content = str(payload.get("content") or "")
    node_type = str(payload.get("node_type") or "character")

    db.add(
        NodeORM(
            id=node_id,
            project_id=record.project_id,
            graph_id=_resolve_graph_id(db, record.project_id, node_type),
            node_type=node_type,
            title=title,
            content=content,
            meta={"tags": ["AI 建议"], "status": "synced"},
            position_x=120.0,
            position_y=120.0,
            sort_order=9999,
        )
    )
    record.target_id = node_id
    db.flush()
    return node_id


def _resolve_endpoint(
    db: Session,
    project_id: str,
    raw_id: str | None,
    pending_id_map: dict[str, str],
) -> str | None:
    """把 payload 里的 source / target 翻译成画布上真实的 node_id。

    优先匹配同批新建节点的 pending_id; 否则按真实 id 查 NodeORM 并校验项目归属;
    任何一步失败都返回 None, 让调用方决定如何降级 (本模块选择静默跳过)。
    """
    if not raw_id:
        return None

    if raw_id in pending_id_map:
        raw_id = pending_id_map[raw_id]

    node = db.get(NodeORM, raw_id)
    if node is None or node.project_id != project_id:
        return None
    return node.id


def _apply_create_edge(
    db: Session,
    record: AgentStagingORM,
    payload: dict[str, Any],
    pending_id_map: dict[str, str],
) -> None:
    """把 staging.payload 翻译成新边; 端点解析失败时记一条 warning 后跳过。"""
    src_raw = payload.get("source")
    tgt_raw = payload.get("target")
    source = _resolve_endpoint(db, record.project_id, src_raw, pending_id_map)
    target = _resolve_endpoint(db, record.project_id, tgt_raw, pending_id_map)

    if source is None or target is None:
        logger.warning(
            "create_edge 跳过: staging=%s project=%s source=%r->%r target=%r->%r",
            record.id, record.project_id, src_raw, source, tgt_raw, target,
        )
        return

    relation_type = str(payload.get("relation_type") or "relates_to")
    label = str(payload.get("label") or relation_type)

    db.add(
        EdgeORM(
            id=uuid.uuid4().hex,
            project_id=record.project_id,
            source=source,
            target=target,
            label=label,
            relation_type=relation_type,
            edge_type=str(payload.get("edge_type") or "smoothstep"),
            sort_order=9999,
        )
    )
    db.flush()

_UPDATABLE_NODE_FIELDS = {"title", "content", "node_type"}


def _apply_update_node(
    db: Session,
    record: AgentStagingORM,
    payload: dict[str, Any],
) -> str | None:
    """把 staging.payload 合并到现有节点; 目标节点不存在或越权时静默跳过。

    LLM 经常用 update_node 给已有节点补设定; payload 只允许覆盖白名单字段,
    其它字段 (id / project_id / position 等) 必须由用户在前端编辑, 防止 AI
    误改画布坐标或归属。
    """
    target_id = record.target_id
    if not target_id:
        return None

    node = db.get(NodeORM, target_id)
    if node is None or node.project_id != record.project_id:
        return None

    for field in _UPDATABLE_NODE_FIELDS:
        if field in payload and payload[field] is not None:
            setattr(node, field, str(payload[field]))

    db.flush()
    return target_id


def _apply_delete_node(db: Session, record: AgentStagingORM) -> str | None:
    """删除节点; 返回被删 node_id 供调用方同步 ChromaDB, 失败/越权返回 None。

    DB 侧已配 ondelete=CASCADE + PRAGMA foreign_keys=ON, 边会自动级联清除;
    这里手动 delete 边作为"防止环境忘开 PRAGMA"的双保险, 不依赖外键也能保证
    画布上不会出现指向已删节点的孤儿边。
    """
    target_id = record.target_id
    if not target_id:
        logger.warning("delete_node 跳过: staging=%s 没有 target_id", record.id)
        return None

    node = db.get(NodeORM, target_id)
    if node is None or node.project_id != record.project_id:
        logger.warning(
            "delete_node 跳过: staging=%s 节点 %s 不在项目 %s 内",
            record.id, target_id, record.project_id,
        )
        return None

    db.query(EdgeORM).filter(
        EdgeORM.project_id == record.project_id,
        (EdgeORM.source == target_id) | (EdgeORM.target == target_id),
    ).delete(synchronize_session=False)
    db.delete(node)
    db.flush()
    return target_id


def _apply_delete_edge(
    db: Session,
    record: AgentStagingORM,
    payload: dict[str, Any],
) -> None:
    """删除单条边。

    优先用 record.target_id 精确锁定 (前端单条接受时由 staging 流程写入);
    退化策略: 用 payload.(source, target, relation_type) 在项目内匹配第一条边。
    匹配不到时静默跳过, 避免 LLM 编一个不存在的 edge_id 触发 500。
    """
    edge = None
    if record.target_id:
        edge = db.get(EdgeORM, record.target_id)
        if edge is not None and edge.project_id != record.project_id:
            edge = None

    if edge is None:
        source = payload.get("source")
        target = payload.get("target")
        if source and target:
            query = db.query(EdgeORM).filter(
                EdgeORM.project_id == record.project_id,
                EdgeORM.source == source,
                EdgeORM.target == target,
            )
            relation = payload.get("relation_type")
            if relation:
                query = query.filter(
                    (EdgeORM.relation_type == relation) | (EdgeORM.label == relation)
                )
            edge = query.first()

    if edge is None:
        logger.warning(
            "delete_edge 跳过: staging=%s 无法定位目标边 target_id=%r payload=%s",
            record.id, record.target_id, payload,
        )
        return

    db.delete(edge)
    db.flush()