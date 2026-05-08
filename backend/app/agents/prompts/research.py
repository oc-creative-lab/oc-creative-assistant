"""Research Agent prompt 模板。

PoC 阶段不接入联网搜索, 只对项目内已有 worldbuilding / character / plot 节点
做结构化整理, 给用户回一份结构化参考资料卡片。
"""

from __future__ import annotations

from app.schemas import RagCurrentNodePayload, RagVectorContextItem


def build_research_prompt(
    current_node: RagCurrentNodePayload,
    vector_context: dict[str, list[RagVectorContextItem]],
    user_query: str,
) -> str:
    """构造 Research Agent 的 prompt。

    Args:
        current_node: 用户当前关注的节点。
        vector_context: 按 node_type 分组的项目内相似节点。
        user_query: 用户输入或留空。

    Returns:
        给 LLM 使用的 prompt 文本。
    """
    references_text = _format_references(vector_context)

    return f"""你是 OC Creative Assistant 中的「Research Agent」。

任务: 基于用户已有的项目资料, 提供结构化参考信息。

你只能输出:
1. 与当前节点相关的参考要点(标题 / 来源节点 ID / 摘要 / 关联说明);
2. 便于后续分类的标签建议;
3. 提醒边界的简短声明。

你不能输出:
1. 完整故事或剧情段落;
2. 脱离用户已有设定的虚构事实(必须基于下方"已有项目资料");
3. 替用户决定最终设定。

请严格基于已有项目资料回答, 凭空生成的"参考资料"会被视为违例。

---

【当前节点】
节点类型: {current_node.type}
节点标题: {current_node.title}
节点内容:
{current_node.content}

---

【已有项目资料】

{references_text}

---

【用户问题】

{user_query or "请基于已有资料整理与当前节点相关的参考要点。"}
"""


def _format_references(vector_context: dict[str, list[RagVectorContextItem]]) -> str:
    """按 node_type 分组展示项目内已有资料, 优先 worldbuilding 以贴合 Research 定位。"""
    sections: list[str] = []

    for node_type in ("worldbuilding", "character", "plot"):
        items = vector_context.get(node_type) or []
        if not items:
            continue

        body = "\n\n".join(
            f"- 节点 ID: {item.id}\n"
            f"  标题: {item.title}\n"
            f"  内容: {item.content}"
            for item in items
        )
        sections.append(f"[{node_type}]\n{body}")

    return "\n\n".join(sections) if sections else "暂无可用项目资料"