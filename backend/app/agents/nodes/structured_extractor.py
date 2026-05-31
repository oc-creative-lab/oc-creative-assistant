"""后台结构化抽取节点（Agent B 之一，first_revision 决策 5 + 改造 1）。

在 persistence_hub 之后运行：从用户最近的自由对话里抽出实体 / 关系，转成
staging（复用 AgentStagingORM），随后【自动落库】（accept_all），并通过流式
通道把"已新增/已更新"的卡片信息推给前端，让用户在对话里看到内联卡片，默认即已
加入、可展开编辑或撤销——不再需要主动审批。

改造 1 的两个要点：
1. 自动落库：写完 staging 立即 accept_all（仍走 AgentStagingORM + canvas_apply，
   不绕过暂存机制），前端用 extraction_applied 事件渲染内联卡片。
2. 按名去重：同名实体已存在则 update_node（把新属性并进 content），而不是再建一张
   新卡片；关系用真实 node_id 连接已存在的节点。

仅在 ``extraction_enabled`` 为真时工作；关闭时 no-op，旧 chat 流程不受影响。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_stream_writer

from app.agents.prompts import load_prompt
from app.agents.schemas import StructuredExtractionOutput
from app.agents.state import AgentState
from app.db.database import SessionLocal
from app.db.models import ChatSessionORM, NodeORM
from app.llm.factory import get_llm_provider
from app.schemas import AgentStagingCreateItem
from app.services.chat_repository import insert_staging_batch


_SYSTEM_PROMPT = load_prompt("structured_extractor")

# 实体类型 → 画布 node_type（与 sub-graph 分区对齐）。
_NODE_TYPE_BY_ENTITY: dict[str, str] = {
    "character": "character",
    "world": "worldbuilding",
    "plot": "plot",
}

# 关系中文 label → relation_type（决定画布连线视觉；落库时用）。
_RELATION_BY_LABEL: dict[str, str] = {
    "属于": "belongs_to",
    "参与": "belongs_to",
    "师徒": "belongs_to",
    "死敌": "conflicts_with",
    "对抗": "conflicts_with",
    "导致": "causes",
    "引发": "causes",
    "发展为": "develops_into",
}


def _merge_content(existing: str, attributes: dict[str, str]) -> str:
    """把新抽到的属性并进已有节点 content，已包含的键值不重复追加。"""
    lines = [line.strip() for line in (existing or "").splitlines() if line.strip()]
    seen = set(lines)
    for key, value in attributes.items():
        entry = f"{key}: {value}".strip()
        if entry and entry not in seen:
            lines.append(entry)
            seen.add(entry)
    return "\n".join(lines)


def _emit_applied(items: list[dict[str, Any]]) -> None:
    """通过 LangGraph custom stream 把"已落库的卡片"推给前端（非流式调用下静默）。"""
    if not items:
        return
    try:
        writer = get_stream_writer()
    except Exception:
        return
    try:
        writer({"type": "extraction_applied", "items": items})
    except Exception:
        pass


def structured_extractor_node(state: AgentState) -> dict[str, Any]:
    if not state.get("extraction_enabled"):
        return {}

    session_id = state.get("session_id", "")
    project_id = state.get("project_id", "")
    assistant_message_id = state.get("assistant_message_id", "")
    if not (session_id and assistant_message_id):
        return {}

    recent = state.get("recent_messages") or []
    history = "\n".join(f"{m['role']}: {m['content']}" for m in recent[-6:]) or "(无)"
    messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"【最近对话】\n{history}\n\n【用户最新消息】\n{state.get('user_message', '')}"
        ),
    ]

    try:
        out = get_llm_provider().structured(messages, StructuredExtractionOutput)
    except Exception:
        return {}

    deferred = [d.model_dump() for d in out.deferred_fields]

    if not out.entities:
        return {"deferred_fields": deferred, "extraction_count": 0}

    items: list[AgentStagingCreateItem] = []
    # 实体名 → 落库时引用的 id（已存在=真实 node_id，新建=pending_id）。
    ref_by_name: dict[str, str] = {}

    # 一次性查重：按 project + node_type + title 找已有节点。
    with SessionLocal() as db:
        pending_seq = 0
        for entity in out.entities:
            node_type = _NODE_TYPE_BY_ENTITY.get(entity.type, "character")
            existing = (
                db.query(NodeORM)
                .filter(
                    NodeORM.project_id == project_id,
                    NodeORM.node_type == node_type,
                    NodeORM.title == entity.name,
                )
                .first()
            )
            if existing is not None:
                # 已有同名卡片 → 更新（把新属性并进 content），不再新建。
                ref_by_name[entity.name] = existing.id
                if entity.attributes:
                    items.append(
                        AgentStagingCreateItem(
                            change_type="update_node",
                            target_id=existing.id,
                            payload={
                                "title": entity.name,
                                "node_type": node_type,
                                "content": _merge_content(existing.content, entity.attributes),
                            },
                            reasoning="后台从对话补充已有卡片",
                        )
                    )
            else:
                pending_seq += 1
                pending_id = f"pending-{pending_seq}"
                ref_by_name[entity.name] = pending_id
                content = "; ".join(f"{k}: {v}" for k, v in entity.attributes.items())
                items.append(
                    AgentStagingCreateItem(
                        change_type="create_node",
                        pending_id=pending_id,
                        payload={"title": entity.name, "content": content, "node_type": node_type},
                        reasoning="后台从对话抽取",
                    )
                )

    for relation in out.relations:
        source = ref_by_name.get(relation.source_name)
        target = ref_by_name.get(relation.target_name)
        if not (source and target):
            continue
        relation_type = _RELATION_BY_LABEL.get(relation.label, "relates_to")
        items.append(
            AgentStagingCreateItem(
                change_type="create_edge",
                payload={
                    "source": source,
                    "target": target,
                    "relation_type": relation_type,
                    "label": relation.label or "关联",
                },
                reasoning="后台从对话抽取",
            )
        )

    if not items:
        return {"deferred_fields": deferred, "extraction_count": 0}

    with SessionLocal.begin() as db:
        if db.get(ChatSessionORM, session_id) is None:
            return {"deferred_fields": deferred, "extraction_count": 0}
        batch_id, _ = insert_staging_batch(
            db,
            session_id=session_id,
            message_id=assistant_message_id,
            project_id=project_id,
            agent_type="structured_extractor",
            items=items,
        )

    # 自动落库：立即 accept_all（仍走 canvas_apply，不绕过 staging）。
    applied = _auto_apply(batch_id)
    _emit_applied(applied)

    return {
        "extraction_batch_id": batch_id,
        "extraction_count": len(items),
        "extraction_applied": applied,
        "deferred_fields": deferred,
    }


def _auto_apply(batch_id: str) -> list[dict[str, Any]]:
    """自动接受整批 staging 并落库，返回"已新增/已更新"的卡片摘要。

    惰性导入 chat_service 避免与 agents 包的循环依赖（chat_service → graph → 本节点）。
    """
    from app.schemas import AgentStagingBatchActionRequest
    from app.services.chat_service import resolve_staging_batch

    try:
        records = resolve_staging_batch(
            batch_id, AgentStagingBatchActionRequest(action="accept_all")
        )
    except Exception:
        return []

    applied: list[dict[str, Any]] = []
    for record in records:
        if record.change_type not in ("create_node", "update_node"):
            continue
        if not record.target_id:
            continue
        payload = record.payload_edited or record.payload
        applied.append(
            {
                "node_id": record.target_id,
                "title": str(payload.get("title") or "未命名"),
                "node_type": str(payload.get("node_type") or "character"),
                "content": str(payload.get("content") or ""),
                "change_type": record.change_type,
            }
        )
    return applied
