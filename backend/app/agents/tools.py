"""LangChain Tools 工厂。

Research / Structure / Simulation agent 在循环里按需调用这些工具收集证据,
把"决定查什么"的权力交还给 LLM, 减少把整个项目知识库无脑塞进 prompt 带来
的噪声。

工具按"询问形态"分两类:
- 相关性 (relevance): search_nodes 按语义命中 top-K, 适合"和 X 有关的"
- 枚举 (enumeration): list_nodes 按 node_type 列出全名单, 适合"项目里都有哪些 X"
两者错配会漏: 用 search_nodes 回答枚举问题, 一定漏掉低相关分的节点。

所有工具都通过闭包绑定 project_id, LLM 可见的 schema 只剩业务参数; agent
节点只需调用 ``make_project_tools(state.project_id)`` 即可拿到当前项目作用域
内的全部只读工具。
"""

from __future__ import annotations

import json

from langchain_core.tools import BaseTool, tool

from app.db.database import SessionLocal
from app.db.models import EdgeORM, NodeORM
from app.rag.retrieval import build_project_vector_context
from app.services.graph_repository import read_project_node, read_project_nodes


_NODE_TYPE_FILTER = {
    "character", "worldbuilding", "plot",
    "idea", "research", "structure",
}


def make_project_tools(project_id: str) -> list[BaseTool]:
    """生成绑定到指定项目的只读工具集。

    内部维护一个 turn 级 search_cache, 让同一轮 ReAct 循环里 LLM 用变体
    query 反复调 search_nodes 时命中已有结果, 避免重复打 chroma。

    cache key 用"词集合"做归一化 (空白拆词 → 排序 → 拼回字符串), 让 LLM
    用词序调换 ("艾琳 导师" / "导师 艾琳") 或微调 top_k 都吃同一缓存; 不
    归一化时 LLM 在 ReAct 里很容易靠改写关键词绕开缓存把 chroma 打爆。
    """
    search_cache: dict[str, str] = {}

    def _cache_key(query: str) -> str:
        # 词序无关 + 重复词消除 + 大小写无关; top_k 不入 key, 取 max top_k 服务所有调用方
        tokens = sorted(set(query.strip().lower().split()))
        return " ".join(tokens)

    @tool
    def search_nodes(query: str, top_k: int = 5) -> str:
        """在当前项目知识库中按语义检索相关节点 (相关性查询)。

        适合"和 X 有关 / 与 Y 相似 / 提到 Z 的内容"这类按相关度排序的问题。
        若用户问的是"项目里都有哪些 X"这种枚举问题, 改用 list_nodes。

        本 turn 内, 调过一次相近关键词组合 (词序无关) 后再发同一组词会
        直接命中缓存, 不会再打 chroma; 也不要用调换词序或者改 top_k 来
        刻意绕开缓存重试, 没有新信息。

        Args:
            query: 检索关键词或自然语言描述。
            top_k: 返回最大节点数; 推荐 3-8。

        Returns:
            JSON 字符串列表, 每项含 id / title / type / content_preview / score。
            检索器异常时返回 "[ERROR] ..." 字符串, 让 LLM 立刻收口而不是
            换关键词重试。
        """
        key = _cache_key(query)
        cached = search_cache.get(key)
        if cached is not None:
            return cached

        bounded_top_k = max(1, min(int(top_k), 10))
        nodes = read_project_nodes(project_id)
        items, store, err = build_project_vector_context(
            project_id, nodes, query, bounded_top_k
        )

        if store == "chroma_unavailable":
            error_payload = (
                f"[ERROR] 检索器暂时不可用: {err}。本轮请直接基于已有上下文"
                f"作答, 不要再调用 search_nodes / list_nodes 重试。"
            )
            search_cache[key] = error_payload
            return error_payload

        result = json.dumps(
            [
                {
                    "id": item.id,
                    "title": item.title,
                    "type": item.type,
                    "content_preview": item.content[:160],
                    "score": round(item.score, 3),
                }
                for item in items
            ],
            ensure_ascii=False,
        )
        search_cache[key] = result
        return result

    @tool
    def list_nodes(node_type: str = "", limit: int = 100) -> str:
        """枚举当前项目里的全部节点, 不走语义检索, 按 node_type 可选过滤。

        适合"项目里都有哪些角色 / 一共写了哪些设定 / 现在的剧情节点都有什么"
        这类要求覆盖全名单的枚举问题; 不要用 search_nodes 回答这类问题, 否则
        会漏掉与查询词相关度低的节点。

        Args:
            node_type: 可选过滤, 六选一: character / worldbuilding / plot
                / idea / research / structure; 空字符串或不在白名单的值表示
                不过滤。
            limit: 最多返回的节点数, 默认 100; 项目较大时 LLM 可缩小到 30-50。

        Returns:
            JSON 字符串列表, 每项含 id / title / type / content_preview。
        """
        nodes = read_project_nodes(project_id)
        if node_type in _NODE_TYPE_FILTER:
            nodes = [n for n in nodes if n.node_type == node_type]
        capped = max(1, min(limit, 200))
        nodes = nodes[:capped]
        return json.dumps(
            [
                {
                    "id": n.id,
                    "title": n.title,
                    "type": n.node_type,
                    "content_preview": (n.content or "")[:120],
                }
                for n in nodes
            ],
            ensure_ascii=False,
        )

    @tool
    def get_node(node_id: str) -> str:
        """读取指定节点的完整正文与标签; 未找到时返回空对象。

        Args:
            node_id: 节点 ID (从 search_nodes / list_nodes / list_neighbors 中获取)。

        Returns:
            JSON 字符串, 含 id / title / type / content / tags。
        """
        node = read_project_node(project_id, node_id)
        if node is None:
            return "{}"
        return json.dumps(
            {
                "id": node.id,
                "title": node.title,
                "type": node.node_type,
                "content": node.content,
                "tags": (node.meta or {}).get("tags", []),
            },
            ensure_ascii=False,
        )

    @tool
    def list_neighbors(node_id: str) -> str:
        """列出某节点画布上一跳直接相连的邻居。

        Args:
            node_id: 节点 ID。

        Returns:
            JSON 列表, 每项含 id / title / type / direction / relation。
        """
        with SessionLocal() as db:
            edges = (
                db.query(EdgeORM)
                .filter(
                    EdgeORM.project_id == project_id,
                    (EdgeORM.source == node_id) | (EdgeORM.target == node_id),
                )
                .all()
            )
            if not edges:
                return "[]"

            neighbor_meta: dict[str, dict[str, str]] = {}
            for edge in edges:
                if edge.source == node_id:
                    other_id, direction = edge.target, "outgoing"
                else:
                    other_id, direction = edge.source, "incoming"
                neighbor_meta[other_id] = {
                    "direction": direction,
                    "relation": edge.label or edge.relation_type,
                }

            nodes = (
                db.query(NodeORM)
                .filter(NodeORM.id.in_(neighbor_meta.keys()))
                .all()
            )
            payload = [
                {
                    "id": node.id,
                    "title": node.title,
                    "type": node.node_type,
                    "direction": neighbor_meta[node.id]["direction"],
                    "relation": neighbor_meta[node.id]["relation"],
                }
                for node in nodes
            ]
        return json.dumps(payload, ensure_ascii=False)

    return [search_nodes, list_nodes, get_node, list_neighbors]