"""Structure Agent prompt 模板。

输入是用户在画布中选中的多节点 + 它们之间的 edges。
Structure 任务专注于把分散节点重组为结构化产出(角色卡 / 关系图 / 剧情大纲),
不依赖向量检索, 因此 prompt 不读取 vector_context, 只看选中子图。
"""

from __future__ import annotations

from app.db.models import EdgeORM, NodeORM


def build_structure_prompt(
    nodes: list[NodeORM],
    edges: list[EdgeORM],
    user_query: str,
) -> str:
    """构造 Structure Agent 的 prompt。

    Args:
        nodes: 用户选中的节点 (按 sort_order 排序)。
        edges: 上述节点之间的 edges (闭合子图, 不包含跨选区的连线)。
        user_query: 用户输入或留空。

    Returns:
        给 LLM 使用的 prompt 文本。
    """
    nodes_text = _format_nodes(nodes)
    edges_text = _format_edges(edges, nodes)

    return f"""你是 OC Creative Assistant 中的「Structure Agent」。

任务: 把分散的节点整理成结构化输出。

你只能输出:
1. 角色卡(姓名 / 一句话简介 / 核心动机 / 关键关系);
2. 关系图三元组([角色A] -[关系]-> [角色B]);
3. 剧情大纲(按节拍排列, 每个节拍标注涉及角色 + 不超过两句话的概述);
4. 提醒边界的简短声明。

你不能输出:
1. 完整对白或剧情段落;
2. 脱离已有节点的虚构事实(必须基于下方"选中节点");
3. 替用户决定最终设定。

请严格基于选中节点和连线整理结构, 不要补充用户未提供的角色或情节。

---

【选中节点】

{nodes_text}

---

【节点间连线】

{edges_text}

---

【用户请求】

{user_query or "请基于上述节点整理为角色卡 + 关系图 + 剧情大纲。"}
"""


def _format_nodes(nodes: list[NodeORM]) -> str:
    if not nodes:
        return "暂无节点"

    return "\n\n".join(
        f"- 节点 ID: {node.id}\n"
        f"  类型: {node.node_type}\n"
        f"  标题: {node.title}\n"
        f"  内容: {node.content}"
        for node in nodes
    )


def _format_edges(edges: list[EdgeORM], nodes: list[NodeORM]) -> str:
    if not edges:
        return "暂无连线"

    title_by_id = {node.id: node.title for node in nodes}

    return "\n".join(
        f"- {title_by_id.get(edge.source, edge.source)} "
        f"-[{edge.label or edge.relation_type}]-> "
        f"{title_by_id.get(edge.target, edge.target)}"
        for edge in edges
    )