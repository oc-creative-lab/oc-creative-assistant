"""读取会话元信息 + 最近消息 + 当前节点, 写入 AgentState 的记忆与上下文字段。

本节点是图的"入口加载器", 后续 RAG / agent 节点都依赖它写入的快照。
``world_brief`` 取自项目级 ProjectORM, 让多轮对话共享同一份世界观语境;
``recent_message_window`` 与 summary_compress 节点的 ``keep_recent`` 配合,
共同决定哪些消息"逐字喂", 哪些进入摘要。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.agents.state import AgentState
from app.core.settings import get_agent_settings
from app.db.database import SessionLocal
from app.db.models import ChatMessageORM, ChatSessionORM, NodeORM, ProjectORM
from app.indexing.document_loader import node_to_current_payload


def _empty_context() -> dict[str, Any]:
    """返回所有"可能跨轮残留"的 AgentState 字段清零增量。

    两个返回路径 (session 不存在 / 正常加载) 都基于这份零值起步, 防止
    LangGraph 复用 checkpoint 时上一轮的 *_output 或 boundary_warnings
    污染本轮装配器的输入。
    """
    return {
        "world_brief": "",
        "conversation_summary": "",
        "recent_messages": [],
        "current_node": None,
        "intent": None,
        "inspiration_output": None,
        "research_output": None,
        "structure_output": None,
        "simulation_output": None,
        "assembler_output": None,
        "boundary_warnings": [],
        "staging_batch_id": None,
        "staging_count": 0,
    }


def load_context_node(state: AgentState) -> dict[str, Any]:
    """从 SQLite 拉取上下文; session 不存在或未提供时返回空骨架。"""
    session_id = state.get("session_id", "")
    selected_ids = state.get("selected_node_ids") or []

    if not session_id:
        return _empty_context()

    window = get_agent_settings().recent_message_window

    with SessionLocal() as db:
        session = db.get(ChatSessionORM, session_id)
        if session is None:
            return _empty_context()

        project = db.get(ProjectORM, session.project_id)
        world_brief = project.world_brief if project is not None else ""

        recent = list(
            db.scalars(
                select(ChatMessageORM)
                .where(ChatMessageORM.session_id == session_id)
                .order_by(ChatMessageORM.created_at.desc())
                .limit(window)
            )
        )
        # SQL 取倒序便于 LIMIT, 这里翻回时间正序喂给 prompt
        recent.reverse()

        current_node_payload = None
        if selected_ids:
            node = db.get(NodeORM, selected_ids[0])
            if node is not None:
                current_node_payload = node_to_current_payload(node)

        return {
            **_empty_context(),
            "world_brief": world_brief,
            "conversation_summary": session.conversation_summary,
            "recent_messages": [
                {"role": message.role, "content": message.content} for message in recent
            ],
            "current_node": current_node_payload,
        }