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
from app.services.web_search_client import (
    WebSearchError,
    WebSearchUnavailable,
    search_web,
)


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

        同一对节点之间可能有多条不同关系的边, 这里逐条返回, 不做邻居去重。
        只回一跳; 若需要"X 的导师的家族"这类跨多跳的链式追问, 改用
        multi_hop_neighbors, 否则会要连续调用本工具自己拼路径。

        Args:
            node_id: 节点 ID。

        Returns:
            JSON 列表, 每项含 id / title / type / direction / relation;
            两节点间有多条边时会出现多项, relation 各不相同。
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

            rows: list[tuple[str, str, str]] = []
            for edge in edges:
                if edge.source == node_id:
                    other_id, direction = edge.target, "outgoing"
                else:
                    other_id, direction = edge.source, "incoming"
                rows.append((other_id, direction, edge.label or edge.relation_type or "related to"))

            titles = {
                n.id: (n.title, n.node_type)
                for n in db.query(NodeORM).filter(NodeORM.id.in_({r[0] for r in rows})).all()
            }
            payload = [
                {
                    "id": other_id,
                    "title": titles[other_id][0],
                    "type": titles[other_id][1],
                    "direction": direction,
                    "relation": relation,
                }
                for other_id, direction, relation in rows
                if other_id in titles
            ]
        return json.dumps(payload, ensure_ascii=False)

    @tool
    def multi_hop_neighbors(
        node_id: str, depth: int = 2, max_nodes: int = 20
    ) -> str:
        """以 node_id 为中心展开 N 跳可达节点, 带最短关系路径回溯。

        适合链式关系问答 ("艾琳的导师的家族" / "A 与 B 之间通过哪些节点相连");
        一跳问题用 list_neighbors 更省 token。

        实现走一次 BFS, 内存中跑完即返; 同 turn 不缓存 (画布关系变化频繁,
        缓存收益不抵失效成本)。

        Args:
            node_id: 起点节点 ID。
            depth: BFS 跳数, 1-3 (默认 2); 超过 3 自动截断, 防止结果爆炸。
            max_nodes: 返回节点数上限, 默认 20, 硬上限 50;
                超过时按 distance 升序保留靠近起点的节点。

        Returns:
            JSON 列表, 每项含 id / title / type / content_preview /
            distance / path; path 形如 "起点 → [关系] → 中间 → [关系] → 终点"。
            起点本身不在结果里; 起点不存在或不属于本项目时返回 "[]"。
        """
        bounded_depth = max(1, min(int(depth), 3))
        bounded_max = max(1, min(int(max_nodes), 50))

        with SessionLocal() as db:
            origin = db.get(NodeORM, node_id)
            if origin is None or origin.project_id != project_id:
                return "[]"
            edges = (
                db.query(EdgeORM)
                .filter(EdgeORM.project_id == project_id)
                .all()
            )
            nodes_by_id = {
                n.id: n
                for n in db.query(NodeORM)
                .filter(NodeORM.project_id == project_id)
                .all()
            }

        # 双向邻接表; relation 优先用 label, 缺失退到 relation_type
        adjacency: dict[str, list[tuple[str, str]]] = {}
        for edge in edges:
            relation = edge.label or edge.relation_type or "关联"
            adjacency.setdefault(edge.source, []).append((edge.target, relation))
            adjacency.setdefault(edge.target, []).append((edge.source, relation))

        # BFS: visited[id] = (distance, prev_id, relation_to_prev)
        visited: dict[str, tuple[int, str | None, str | None]] = {
            node_id: (0, None, None)
        }
        frontier: list[str] = [node_id]
        while frontier:
            current = frontier.pop(0)
            current_dist = visited[current][0]
            if current_dist >= bounded_depth:
                continue
            for neighbor_id, relation in adjacency.get(current, []):
                if neighbor_id in visited:
                    continue
                visited[neighbor_id] = (current_dist + 1, current, relation)
                frontier.append(neighbor_id)

        def _trace_path(end_id: str) -> str:
            """从终点回溯起点, 拼成 "起点 → [关系] → ... → 终点" 字符串。"""
            chain: list[str] = []
            cursor: str | None = end_id
            while cursor is not None:
                node = nodes_by_id.get(cursor)
                chain.append(node.title if node else cursor)
                _, prev, relation = visited[cursor]
                if prev is not None and relation:
                    chain.append(f"[{relation}]")
                cursor = prev
            return " → ".join(reversed(chain))

        result_ids = sorted(
            (vid for vid in visited if vid != node_id and vid in nodes_by_id),
            key=lambda vid: visited[vid][0],
        )[:bounded_max]

        payload = [
            {
                "id": vid,
                "title": nodes_by_id[vid].title,
                "type": nodes_by_id[vid].node_type,
                "content_preview": (nodes_by_id[vid].content or "")[:120],
                "distance": visited[vid][0],
                "path": _trace_path(vid),
            }
            for vid in result_ids
        ]

        return json.dumps(payload, ensure_ascii=False)

    @tool
    def web_search(query: str, top_k: int = 5) -> str:
        """在互联网上检索外部事实, 仅用于项目知识库无法回答的"现实参考"问题。

        典型用途:
        - 现实考据 (中世纪盔甲形制 / 真实历史事件 / 物理常识 / 武器名称)
        - 实时信息 (天气 / 新闻 / 当前日期附近的事实)
        - 第三方知识 (某个外部模型 / 框架 / 库的规格)

        不要用于:
        - 项目内剧情 / 角色 / 设定问题 — 改用 search_nodes / list_nodes
        - 询问 Agent 自身 (你用什么模型 / 你叫什么) — 这是系统信息, web 无法回答

        本 turn 内同关键词组合 (词序无关) 会命中缓存; 不要刻意改写关键词重打,
        没有新信息。

        Args:
            query: 检索关键词或自然语言问句。
            top_k: 返回最多结果数, 推荐 3-6。

        Returns:
            JSON 字符串, 含 answer (Tavily 合成的简短答案) 与 hits 列表
            (每项含 title / url / snippet / score)。web 不可用时返回
            "[ERROR] ..." 字符串, 让 LLM 立刻收口。
        """
        key = _cache_key(query)
        cached = search_cache.get(f"web::{key}")
        if cached is not None:
            return cached

        try:
            response = search_web(query, top_k)
        except WebSearchUnavailable as exc:
            error_payload = (
                f"[ERROR] {exc}。本轮请基于已有上下文与项目知识库作答, "
                f"不要再调用 web_search 重试。"
            )
            search_cache[f"web::{key}"] = error_payload
            return error_payload
        except WebSearchError as exc:
            error_payload = f"[ERROR] web_search 调用失败: {exc}"
            search_cache[f"web::{key}"] = error_payload
            return error_payload

        result = json.dumps(
            {
                "answer": response.answer,
                "hits": [
                    {
                        "title": hit.title,
                        "url": hit.url,
                        "snippet": hit.snippet,
                        "score": round(hit.score, 3),
                    }
                    for hit in response.hits
                ],
            },
            ensure_ascii=False,
        )
        search_cache[f"web::{key}"] = result
        return result

    return [
        search_nodes,
        list_nodes,
        get_node,
        list_neighbors,
        multi_hop_neighbors,
        web_search,
    ]
