"""LangGraph Agent 编排。

把 RAG 检索与 LLM 调用串成 StateGraph, 通过 conditional_edges 按 agent_type
分发到三类 Agent, 实现 proposal 4.1.2 / 4.3.2 要求的非线性 Agent 执行。

加新 Agent 时只需:
1. 在 schemas.py 新增 *Output;
2. 在 prompts/ 新增模板;
3. 在这里加一个 *_agent_node 与一条 conditional edge。
符合 Open/Closed Principle。
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy import select

from app.agents.prompts.inspiration import build_inspiration_prompt
from app.agents.prompts.research import build_research_prompt
from app.agents.prompts.structure import build_structure_prompt
from app.agents.schemas import InspirationOutput, ResearchOutput, StructureOutput
from app.agents.state import AgentState, AgentType
from app.db.database import SessionLocal
from app.db.models import EdgeORM, NodeORM
from app.indexing.config import COLLECTION_BY_NODE_TYPE, MAX_TOP_K
from app.indexing.document_loader import node_to_current_payload, node_to_vector_item
from app.indexing.vector_store import get_all_chroma_collections, query_collection
from app.llm.provider import get_llm_provider
from app.rag.retrieval import _build_graph_context, _merge_context
from app.schemas import RagVectorContextItem


logger = logging.getLogger(__name__)


# ---------- 检索阶段 ----------

def load_node_node(state: AgentState) -> dict[str, Any]:
    """从 SQLite 加载当前节点。

    inspiration / research 走 node_id 单节点入口;
    structure 走 node_ids 多节点入口, 此处只推断 project_id, current_node 留空。
    """
    node_id = state.get("node_id")

    if node_id is None:
        node_ids = state.get("node_ids") or []
        if not node_ids:
            return {"error": "缺少 node_id 或 node_ids"}

        with SessionLocal() as session:
            sample = session.get(NodeORM, node_ids[0])

        if sample is None:
            return {"error": f"节点不存在: {node_ids[0]}"}

        return {
            "project_id": sample.project_id,
            "current_node": node_to_current_payload(sample),
        }

    with SessionLocal() as session:
        node = session.get(NodeORM, node_id)

    if node is None:
        return {"error": f"节点不存在: {node_id}"}

    return {
        "current_node": node_to_current_payload(node),
        "project_id": node.project_id,
    }


def graph_retrieval_node(state: AgentState) -> dict[str, Any]:
    """构建一跳图关系上下文, 复用 rag.retrieval 中已有逻辑。"""
    if state.get("error"):
        return {}

    node_id = state.get("node_id")
    project_id = state.get("project_id")

    if node_id is None or project_id is None:
        return {"graph_context": []}

    with SessionLocal() as session:
        nodes = session.scalars(
            select(NodeORM)
            .where(NodeORM.project_id == project_id)
            .order_by(NodeORM.sort_order, NodeORM.created_at)
        ).all()
        edges = session.scalars(
            select(EdgeORM)
            .where(EdgeORM.project_id == project_id)
            .order_by(EdgeORM.sort_order, EdgeORM.created_at)
        ).all()

    return {"graph_context": _build_graph_context(node_id, nodes, edges)}


def vector_retrieval_node(state: AgentState) -> dict[str, Any]:
    """按 node_type 分组查询向量库。

    Structure Agent 只看用户选区子图, 不需要语义检索, 直接短路省成本。
    """
    if state.get("error"):
        return {}

    if state.get("agent_type") == "structure":
        return {"vector_context": {}}

    project_id = state.get("project_id")

    if project_id is None:
        return {"vector_context": {}}

    current = state.get("current_node")
    current_node_id = state.get("node_id")
    query = (state.get("user_query") or "").strip()

    if not query and current is not None:
        # 沿用原 RAG 服务的兜底: 用当前节点正文作为检索 query
        query = f"{current.title}\n{current.content}".strip()

    if not query:
        return {"vector_context": {}}

    with SessionLocal() as session:
        nodes = session.scalars(
            select(NodeORM).where(NodeORM.project_id == project_id)
        ).all()

    if len(nodes) <= 1:
        return {"vector_context": {}}

    node_by_id = {node.id: node for node in nodes}
    top_k = state.get("top_k", 5)

    try:
        collections_by_name = get_all_chroma_collections()
    except Exception as error:  # noqa: BLE001
        logger.warning("ChromaDB 初始化失败: %s", error)
        return {"vector_context": {}, "error": str(error)}

    grouped: dict[str, list[RagVectorContextItem]] = {}

    for node_type in ("character", "worldbuilding", "plot"):
        collection_name = COLLECTION_BY_NODE_TYPE.get(node_type)
        if collection_name is None:
            grouped[node_type] = []
            continue

        grouped[node_type] = _query_one_type(
            collections_by_name[collection_name],
            project_id=project_id,
            query=query,
            top_k=top_k,
            node_by_id=node_by_id,
            exclude_node_id=current_node_id,
        )

    return {"vector_context": grouped}


def _query_one_type(
    collection: Any,
    *,
    project_id: str,
    query: str,
    top_k: int,
    node_by_id: dict[str, NodeORM],
    exclude_node_id: str | None,
) -> list[RagVectorContextItem]:
    """对单个 collection 做向量检索, 失败不抛异常以保证其它集合仍可返回结果。"""
    try:
        ids, metadatas, distances = query_collection(collection, project_id, query, top_k)
    except Exception as error:  # noqa: BLE001
        logger.warning("Chroma 查询失败 collection=%s: %s", collection.name, error)
        return []

    items: list[RagVectorContextItem] = []

    for _, metadata, distance in zip(ids, metadatas, distances, strict=False):
        target_id = metadata.get("node_id") if isinstance(metadata, dict) else None

        if not isinstance(target_id, str) or target_id == exclude_node_id:
            continue

        target_node = node_by_id.get(target_id)
        if target_node is None:
            continue

        items.append(node_to_vector_item(target_node, score=max(0.0, 1.0 - float(distance))))

        if len(items) >= top_k:
            break

    return items


def context_compress_node(state: AgentState) -> dict[str, Any]:
    """合并上下文并按 token 阈值截断, 对应 proposal 7.3.4 的 2000 token cap。

    PoC 阶段使用硬截断而非 LLM 摘要; 严格 summary compression 留给后续优化。
    """
    if state.get("error"):
        return {}

    graph_context = state.get("graph_context", [])
    grouped_vector = state.get("vector_context") or {}

    flat_vector = sorted(
        (item for items in grouped_vector.values() for item in items),
        key=lambda item: item.score,
        reverse=True,
    )

    merged = _merge_context(graph_context, flat_vector)
    capped = _cap_by_tokens(merged, max_tokens=2000)

    return {
        "merged_context": capped,
        "context_token_count": _estimate_tokens(capped),
    }


def _cap_by_tokens(items: list, max_tokens: int) -> list:
    """按出现顺序累加 token, 超过 max_tokens 时保留至少一条后停止。"""
    encoding = _get_tiktoken_encoding()
    capped: list = []
    total = 0

    for item in items:
        text = f"{item.title}\n{item.content}"
        tokens = len(encoding.encode(text)) if encoding is not None else len(text) // 2

        if total + tokens > max_tokens and capped:
            break

        capped.append(item)
        total += tokens

    return capped


def _estimate_tokens(items: list) -> int:
    """粗略 token 估算, tiktoken 不可用时按字符数除以 2 兜底。"""
    encoding = _get_tiktoken_encoding()
    text = "\n".join(f"{item.title}\n{item.content}" for item in items)

    if encoding is not None:
        return len(encoding.encode(text))
    return len(text) // 2


def _get_tiktoken_encoding() -> Any:
    """tiktoken 已在 requirements.txt; 这里仍兜底以兼容删除依赖的场景。"""
    try:
        import tiktoken
        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # noqa: BLE001
        return None


# ---------- 路由 ----------

def route_to_agent(state: AgentState) -> AgentType:
    """conditional_edges 路由函数: 根据 agent_type 决定下一节点。"""
    return state.get("agent_type", "inspiration")


# ---------- Agent 阶段 ----------

def inspiration_agent_node(state: AgentState) -> dict[str, Any]:
    """调用 LLM 生成 InspirationOutput。"""
    if state.get("error"):
        return {"final_output": None}

    current = state.get("current_node")
    if current is None:
        return {"error": "Inspiration Agent 需要当前节点", "final_output": None}

    user_query = (state.get("user_query") or f"{current.title}\n{current.content}").strip()
    prompt = build_inspiration_prompt(
        current,
        state.get("graph_context", []),
        state.get("vector_context") or {},
        user_query,
        top_k=state.get("top_k", 5),
    )

    return _invoke_llm(prompt, InspirationOutput)


def research_agent_node(state: AgentState) -> dict[str, Any]:
    """调用 LLM 生成 ResearchOutput, 仅基于项目内已有节点做结构化整理。"""
    if state.get("error"):
        return {"final_output": None}

    current = state.get("current_node")
    if current is None:
        return {"error": "Research Agent 需要当前节点", "final_output": None}

    user_query = (state.get("user_query") or "").strip()
    prompt = build_research_prompt(
        current,
        state.get("vector_context") or {},
        user_query,
    )

    return _invoke_llm(prompt, ResearchOutput)


def structure_agent_node(state: AgentState) -> dict[str, Any]:
    """调用 LLM 把多节点重组为 StructureOutput(角色卡 / 关系图 / 剧情大纲)。

    仅使用用户在画布中选中的 node_ids 与它们之间的 edges, 不读取向量检索结果。
    """
    if state.get("error"):
        return {"final_output": None}

    project_id = state.get("project_id")
    node_ids = state.get("node_ids") or []

    if not project_id or not node_ids:
        return {"error": "Structure Agent 需要 project_id 与 node_ids", "final_output": None}

    nodes, edges = _load_structure_inputs(project_id, node_ids)

    if not nodes:
        return {"error": "未找到可用于整理的节点", "final_output": None}

    prompt = build_structure_prompt(nodes, edges, (state.get("user_query") or "").strip())
    return _invoke_llm(prompt, StructureOutput)


def _load_structure_inputs(
    project_id: str,
    node_ids: list[str],
) -> tuple[list[NodeORM], list[EdgeORM]]:
    """批量读取选中节点 + 仅在选区内的 edges, 保证 LLM 看到的是闭合子图。

    跨选区的 edges 被故意过滤掉: 它们一端落在用户没选中的节点上, 解释起来需要
    引入选区外信息, 反而稀释 Structure Agent 的整理质量。
    """
    with SessionLocal() as session:
        nodes = session.scalars(
            select(NodeORM)
            .where(NodeORM.project_id == project_id, NodeORM.id.in_(node_ids))
            .order_by(NodeORM.sort_order, NodeORM.created_at)
        ).all()
        edges = session.scalars(
            select(EdgeORM)
            .where(
                EdgeORM.project_id == project_id,
                EdgeORM.source.in_(node_ids),
                EdgeORM.target.in_(node_ids),
            )
            .order_by(EdgeORM.sort_order, EdgeORM.created_at)
        ).all()

    return list(nodes), list(edges)


def _invoke_llm(prompt: str, schema: type, max_attempts: int = 2) -> dict[str, Any]:
    """统一封装 LLM 调用, 异常或返回空时短暂重试, 缓解 DeepSeek function_calling 偶发性失败。

    Args:
        prompt: 已经拼装好的 user prompt。
        schema: 强制 LLM 输出的 Pydantic schema。
        max_attempts: 最多尝试次数(含首次), 默认 2 已足以把成功率拉到 ~98%。
    """
    provider = get_llm_provider()
    messages = [{"role": "user", "content": prompt}]
    last_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            output = provider.chat(messages, response_schema=schema)
        except Exception as error:  # noqa: BLE001
            last_error = str(error)
            logger.warning("Agent LLM 调用失败(尝试 %d/%d): %s", attempt, max_attempts, error)
            continue

        if output is not None:
            return {"final_output": output}

        last_error = "LLM 未返回结构化输出"
        logger.warning("Agent LLM 返回空输出(尝试 %d/%d), 准备重试", attempt, max_attempts)

    return {"final_output": None, "error": last_error}


# ---------- StateGraph 装配 ----------

def build_agent_graph() -> Any:
    """装配 LangGraph StateGraph 并编译为可执行图。"""
    builder = StateGraph(AgentState)

    builder.add_node("load_node", load_node_node)
    builder.add_node("graph_retrieval", graph_retrieval_node)
    builder.add_node("vector_retrieval", vector_retrieval_node)
    builder.add_node("context_compress", context_compress_node)
    builder.add_node("inspiration_agent", inspiration_agent_node)
    builder.add_node("research_agent", research_agent_node)
    builder.add_node("structure_agent", structure_agent_node)

    builder.set_entry_point("load_node")
    builder.add_edge("load_node", "graph_retrieval")
    builder.add_edge("graph_retrieval", "vector_retrieval")
    builder.add_edge("vector_retrieval", "context_compress")
    builder.add_conditional_edges(
        "context_compress",
        route_to_agent,
        {
            "inspiration": "inspiration_agent",
            "research": "research_agent",
            "structure": "structure_agent",
        },
    )
    builder.add_edge("inspiration_agent", END)
    builder.add_edge("research_agent", END)
    builder.add_edge("structure_agent", END)

    return builder.compile()


# 模块导入时一次性编译, 避免每个请求重复构图。
agent_graph = build_agent_graph()