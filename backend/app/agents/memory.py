"""多层记忆 prompt 拼装器。

把 AgentState 里 world_brief / key_facts / conversation_summary /
recent_messages / current_nodes / merged_context 六块上下文按固定结构
拼成中文简报, 让所有 agent 节点的 HumanMessage 都用同一种格式注入背景信息。

升级点 (v2):
- 新增"核心事实层": 由 summary_compress 累积抽取的 key_facts, 跨轮不丢失,
  避免长对话后早期关键设定被滚动摘要覆盖
- intent-aware 装配: small_talk 走精简版省 token, 其余 intent 走全套
"""

from __future__ import annotations

from app.agents.state import AgentState
from app.schemas import RagCurrentNodePayload, RagMergedContextItem


_RECENT_TRUNCATE = 200
_MERGED_TRUNCATE = 120
_CURRENT_NODE_TRUNCATE = 200
_KEY_FACTS_MAX = 12


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


def _format_key_facts(facts: list[str]) -> str:
    """累积式核心事实, 只取最近 _KEY_FACTS_MAX 条, 避免无限膨胀。"""
    if not facts:
        return "(尚无沉淀)"
    tail = facts[-_KEY_FACTS_MAX:]
    return "\n".join(f"- {fact}" for fact in tail)


def build_memory_block(state: AgentState, intent: str | None = None) -> str:
    """按 intent 选择性装配多层记忆段落。

    small_talk 只需要世界观纲要 + 最近对话, 不需要画布检索结果与核心事实层,
    省 token 也避免 LLM 把项目里的角色名误用进闲聊回复。其它 intent 走全套。
    """
    world_brief = (state.get("world_brief") or "").strip()
    seed_context = (state.get("seed_context") or "").strip()
    key_facts = state.get("key_facts") or []
    summary = (state.get("conversation_summary") or "").strip()
    recent = state.get("recent_messages") or []
    merged = state.get("merged_context") or []
    current_node_section = _format_current_nodes(state.get("current_nodes") or [])

    seed_section = f"【项目种子 (当前全貌快照)】\n{seed_context}" if seed_context else ""

    if intent == "small_talk":
        sections = [f"【世界观纲要】\n{world_brief or '(尚未沉淀)'}"]
        if seed_section:
            sections.append(seed_section)
        sections.append(f"【最近对话】\n{_format_recent_messages(recent)}")
        return "\n\n".join(sections)

    sections = [
        f"【世界观纲要】\n{world_brief or '(尚未沉淀)'}",
    ]
    if seed_section:
        sections.append(seed_section)
    sections += [
        f"【核心事实层 (跨轮沉淀, 不会被摘要覆盖)】\n{_format_key_facts(key_facts)}",
        f"【过往对话摘要】\n{summary or '(尚无)'}",
        f"【最近对话】\n{_format_recent_messages(recent)}",
        f"【画布相关节点】\n{_format_merged_context(merged)}",
    ]
    if current_node_section:
        sections.append(current_node_section)
    return "\n\n".join(sections)