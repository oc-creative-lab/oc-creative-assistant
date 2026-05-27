"""多层记忆 prompt 拼装器。

把 AgentState 里 world_brief / conversation_summary / recent_messages /
current_node / merged_context 五块上下文按固定结构拼成一段中文文本, 让三个
agent 节点的 HumanMessage 都用同一种"看起来像简报"的格式注入背景信息, 避免
每个节点各自拼字符串导致风格漂移。
"""

from __future__ import annotations

from app.agents.state import AgentState
from app.schemas import RagCurrentNodePayload, RagMergedContextItem


_RECENT_TRUNCATE = 200
_MERGED_TRUNCATE = 120
_CURRENT_NODE_TRUNCATE = 200


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _format_recent_messages(messages: list[dict]) -> str:
    if not messages:
        return "(暂无)"
    lines: list[str] = []
    for message in messages:
        role = message.get("role", "?")
        content = _truncate(message.get("content") or "", _RECENT_TRUNCATE)
        lines.append(f"- {role}: {content}")
    return "\n".join(lines)


def _format_merged_context(items: list[RagMergedContextItem]) -> str:
    if not items:
        return "(暂无)"
    return "\n".join(
        f"- [{item.id}] {item.title} ({item.type}): "
        f"{_truncate(item.content, _MERGED_TRUNCATE)}"
        for item in items
    )


def _format_current_nodes(nodes: list[RagCurrentNodePayload]) -> str:
    if not nodes:
        return ""
    if len(nodes) == 1:
        node = nodes[0]
        body = _truncate(node.content, _CURRENT_NODE_TRUNCATE)
        return f"【当前节点】\n[{node.id}] {node.title} ({node.type}): {body}"
    lines = [f"【当前节点 (共 {len(nodes)} 个, 用户希望同时关注)】"]
    for node in nodes:
        body = _truncate(node.content, _CURRENT_NODE_TRUNCATE)
        lines.append(f"- [{node.id}] {node.title} ({node.type}): {body}")
    return "\n".join(lines)


def build_memory_block(state: AgentState) -> str:
    """生成插入 HumanMessage 头部的多层记忆段落; 没有 current_node 时该段省略。"""
    world_brief = (state.get("world_brief") or "").strip()
    summary = (state.get("conversation_summary") or "").strip()
    recent = state.get("recent_messages") or []
    merged = state.get("merged_context") or []
    current_node_section = _format_current_nodes(state.get("current_nodes") or [])

    sections = [
        f"【世界观纲要】\n{world_brief or '(尚未沉淀)'}",
        f"【过往对话摘要】\n{summary or '(尚无)'}",
        f"【最近对话】\n{_format_recent_messages(recent)}",
        f"【画布相关节点】\n{_format_merged_context(merged)}",
    ]
    if current_node_section:
        sections.append(current_node_section)
    return "\n\n".join(sections)