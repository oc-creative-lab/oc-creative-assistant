"""持久化中枢节点。

每轮把以下副作用一并落库:
1. 追加 user / assistant 两条 ChatMessage
2. 如果当轮 agent 输出含 proposed_changes, 写入同一 batch_id 的 AgentStaging,
   等用户在前端 staging 面板接受 / 编辑 / 拒绝

写入失败时不让整张图崩溃: session 不存在直接静默跳过, 让 graph.invoke 仍能
返回一份 in-memory 的 assembler_output 给调用方做兜底。
"""

from __future__ import annotations

from typing import Any

from app.agents.schemas import ProposedChange
from app.agents.state import AgentState
from app.db.database import SessionLocal
from app.db.models import ChatSessionORM
from app.schemas import AgentStagingCreateItem
from app.services.chat_repository import append_message, insert_staging_batch


_OUTPUT_KEY_BY_INTENT: dict[str, str] = {
    "inspiration": "inspiration_output",
    "research": "research_output",
    "structure": "structure_output",
}
"""仅这三类 agent 会产出 proposed_changes; simulation 物理隔离, 不进。"""


def _collect_proposed_changes(state: AgentState) -> tuple[list[ProposedChange], str]:
    """从当前 intent 对应 agent 的输出里取 proposed_changes; 没有就回空列表。

    agent_type 取 intent.primary, 让 staging 表能按 agent 来源分组展示。
    """
    intent = state.get("intent")
    primary = intent.primary if intent is not None else ""
    output_key = _OUTPUT_KEY_BY_INTENT.get(primary)
    if output_key is None:
        return [], primary

    output = state.get(output_key)
    if output is None:
        return [], primary

    changes = list(getattr(output, "proposed_changes", []) or [])
    return changes, primary


def _to_staging_items(changes: list[ProposedChange]) -> list[AgentStagingCreateItem]:
    """ProposedChange (agent 内部模型) → AgentStagingCreateItem (持久化模型)。"""
    return [
        AgentStagingCreateItem(
            change_type=change.change_type,
            target_id=change.target_id,
            pending_id=change.pending_id,
            payload=change.payload,
            reasoning=change.reason,
        )
        for change in changes
    ]


def persistence_hub_node(state: AgentState) -> dict[str, Any]:
    session_id = state.get("session_id", "")
    project_id = state.get("project_id", "")
    user_message = state.get("user_message", "").strip()
    assembler = state.get("assembler_output")

    if not session_id or assembler is None:
        return {}

    proposed_changes, agent_type = _collect_proposed_changes(state)
    staging_items = _to_staging_items(proposed_changes)

    with SessionLocal.begin() as db:
        if db.get(ChatSessionORM, session_id) is None:
            return {}

        if user_message:
            append_message(db, session_id=session_id, role="user", content=user_message)

        meta: dict[str, Any] = {
            "agent_type": agent_type,
            "cited_node_ids": list(assembler.cited_node_ids),
            "staging_summary": assembler.staging_summary,
        }
        assistant_message = append_message(
            db,
            session_id=session_id,
            role="assistant",
            content=assembler.reply_text,
            meta=meta,
        )
        assistant_message_id = assistant_message.id

        batch_id: str | None = None
        if staging_items:
            batch_id, _ = insert_staging_batch(
                db,
                session_id=session_id,
                message_id=assistant_message_id,
                project_id=project_id,
                agent_type=agent_type,
                items=staging_items,
            )

    return {
        "assistant_message_id": assistant_message_id,
        "staging_batch_id": batch_id,
        "staging_count": len(staging_items),
    }