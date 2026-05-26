"""边界检查节点。

跑在 chat_assembler 之前, 对当轮 agent 输出的 proposed_changes 做确定性校验,
把不合规的项过滤掉, 把原因写到 ``boundary_warnings`` 里供下游引用; 让
chat_assembler 能在回复里如实说明被跳过的原因, 避免用户接受空壳 staging。

校验只跑硬规则, 不调 LLM:
- create_node: title / content 长度, node_type 白名单
- create_edge: source / target 必须是同 batch 的 pending_id 或项目内真实 node_id,
  禁止自环
- update_node: target_id 必须命中现有节点, payload 至少含一个可更新字段
- 整批: pending_id 不重复, 单批变更数 ≤ 上限

与 canvas_apply 的"防御性跳过"互为前后呼应: canvas_apply 是落库前最后一道
兜底, 这里是最早一道挡板, 让用户能在回复里第一时间看到"哪一项为什么没过"。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.schemas import ProposedChange
from app.agents.state import AgentState
from app.db.database import SessionLocal
from app.db.models import NodeORM


# 仅这几个 intent 的 agent 会产出 proposed_changes; simulation 物理隔离, 不进。
_OUTPUT_KEY_BY_INTENT: dict[str, str] = {
    "inspiration": "inspiration_output",
    "research": "research_output",
    "structure": "structure_output",
}

_VALID_NODE_TYPES = {
    "character", "worldbuilding", "plot",
    "idea", "research", "structure",
}
_UPDATABLE_FIELDS = {"title", "content", "node_type"}
_TITLE_MAX = 100
_CONTENT_MAX = 2000
_MAX_CHANGES_PER_BATCH = 10
_AGENTS_WITH_CHANGES = {"inspiration", "research", "structure"}


def boundary_check_node(state: AgentState) -> dict[str, Any]:
    """对当前 intent 对应 agent 的 proposed_changes 做边界校验。

    跑硬规则过滤掉不合规的项, 把原因写到 ``boundary_warnings`` 里供下游
    chat_assembler 引用; 让用户在回复里第一时间看到"哪一项为什么被跳过"。
    """
    intent = state.get("intent")
    if intent is None or intent.primary not in _AGENTS_WITH_CHANGES:
        return {}

    output_key = f"{intent.primary}_output"
    output = state.get(output_key)
    if output is None:
        return {}

    changes = list(getattr(output, "proposed_changes", []) or [])
    if not changes:
        return {}

    accepted, warnings = _filter_changes(changes, state.get("project_id", ""))
    if not warnings and len(accepted) == len(changes):
        return {}

    updates: dict[str, Any] = {"boundary_warnings": warnings}
    if len(accepted) != len(changes):
        updates[output_key] = output.model_copy(update={"proposed_changes": accepted})
    return updates


def _filter_changes(
    changes: list[ProposedChange],
    project_id: str,
) -> tuple[list[ProposedChange], list[str]]:
    """跑全部规则, 返回 (通过的 changes, 警告描述列表)。

    去重维度: create_node 看 pending_id, create_edge 看 (source, target,
    relation_type) 三元组, update_node 看 (target_id, payload 关键字段) 组合。
    LLM 偶尔会把"想清楚的一条"复制 N 遍塞进 list, 这层去重在 batch 内做硬清除。
    """
    warnings: list[str] = []

    if len(changes) > _MAX_CHANGES_PER_BATCH:
        warnings.append(
            f"agent 一次提议了 {len(changes)} 处变更, 超过单轮上限 "
            f"{_MAX_CHANGES_PER_BATCH}; 仅保留前 {_MAX_CHANGES_PER_BATCH} 条。"
        )
        changes = changes[:_MAX_CHANGES_PER_BATCH]

    pending_ids: set[str] = set()
    seen_signatures: set[tuple] = set()
    duplicate_indices: set[int] = set()

    for idx, change in enumerate(changes):
        if change.change_type == "create_node" and change.pending_id:
            if change.pending_id in pending_ids:
                duplicate_indices.add(idx)
                warnings.append(
                    f"第 {idx + 1} 条 create_node 的 pending_id="
                    f"{change.pending_id!r} 与同 batch 内已有项重复, 跳过。"
                )
            else:
                pending_ids.add(change.pending_id)

        signature = _signature_of(change)
        if signature is None:
            continue
        if signature in seen_signatures:
            duplicate_indices.add(idx)
            warnings.append(
                f"第 {idx + 1} 条 {change.change_type} 与同 batch 内已有项内容"
                f" 完全相同, 跳过。"
            )
        else:
            seen_signatures.add(signature)

    accepted: list[ProposedChange] = []
    with SessionLocal() as db:
        for idx, change in enumerate(changes):
            if idx in duplicate_indices:
                continue
            problem = _check_one(change, db, project_id, pending_ids)
            if problem is None:
                accepted.append(change)
            else:
                warnings.append(f"第 {idx + 1} 条 {change.change_type}: {problem}")

    return accepted, warnings


def _signature_of(change: ProposedChange) -> tuple | None:
    """提取一条变更的"内容指纹"用于跨条去重; 不构成指纹时返回 None 跳过去重。"""
    payload = change.payload or {}

    if change.change_type == "create_node":
        return (
            "create_node",
            (str(payload.get("title") or "")).strip().lower(),
            payload.get("node_type"),
        )

    if change.change_type == "create_edge":
        source = payload.get("source")
        target = payload.get("target")
        relation = payload.get("relation_type") or payload.get("label") or ""
        if not source or not target:
            return None
        return ("create_edge", source, target, relation)

    if change.change_type == "update_node":
        return (
            "update_node",
            change.target_id,
            (str(payload.get("title") or "")).strip().lower(),
            (str(payload.get("content") or "")).strip().lower(),
            payload.get("node_type"),
        )

    if change.change_type == "delete_node":
        return ("delete_node", change.target_id)

    if change.change_type == "delete_edge":
        return (
            "delete_edge",
            change.target_id,
            payload.get("source"),
            payload.get("target"),
            payload.get("relation_type") or payload.get("label") or "",
        )
    return None


def _check_one(
    change: ProposedChange,
    db: Session,
    project_id: str,
    pending_ids: set[str],
) -> str | None:
    """对单条变更跑全部规则; 返回 None 表示通过, 否则返回拒绝原因。"""
    payload = change.payload or {}

    if change.change_type == "create_node":
        title = (str(payload.get("title") or "")).strip()
        if not title:
            return "缺少 title。"
        if len(title) > _TITLE_MAX:
            return f"title 长度 {len(title)} 超过 {_TITLE_MAX} 上限。"
        content = str(payload.get("content") or "")
        if len(content) > _CONTENT_MAX:
            return f"content 长度 {len(content)} 超过 {_CONTENT_MAX} 上限。"
        if payload.get("node_type") not in _VALID_NODE_TYPES:
            return (
                f"node_type={payload.get('node_type')!r} 不在白名单 "
                f"{sorted(_VALID_NODE_TYPES)}。"
            )
        return None

    if change.change_type == "create_edge":
        source = payload.get("source")
        target = payload.get("target")
        if not source or not target:
            return "source 或 target 为空。"
        if source == target:
            return "source 与 target 相同, 拒绝自环边。"
        for label, raw in (("source", source), ("target", target)):
            if raw in pending_ids:
                continue
            node = db.get(NodeORM, raw)
            if node is None or node.project_id != project_id:
                return (
                    f"{label}={raw!r} 既不是同 batch 的 pending_id, 也不是项目"
                    " 内的真实 node_id。"
                )
        return None

    if change.change_type == "update_node":
        if not change.target_id:
            return "缺少 target_id。"
        node = db.get(NodeORM, change.target_id)
        if node is None or node.project_id != project_id:
            return f"target_id={change.target_id!r} 在项目内找不到对应节点。"
        if not any(field in payload for field in _UPDATABLE_FIELDS):
            return f"payload 必须含至少一个可更新字段 {sorted(_UPDATABLE_FIELDS)}。"
        return None

    if change.change_type == "delete_node":
        if not change.target_id:
            return "缺少 target_id。"
        node = db.get(NodeORM, change.target_id)
        if node is None or node.project_id != project_id:
            return f"target_id={change.target_id!r} 在项目内找不到对应节点。"
        return None

    if change.change_type == "delete_edge":
        if change.target_id:
            return None  # 真实 edge_id 由 canvas_apply 落库时再做项目归属校验
        payload_src = payload.get("source")
        payload_tgt = payload.get("target")
        if not payload_src or not payload_tgt:
            return "缺少 target_id, 或缺少 payload.source / payload.target 三元组。"
        return None

    return f"暂不支持的 change_type={change.change_type!r}。"