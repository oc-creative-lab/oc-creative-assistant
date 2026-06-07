"""LangChain Tools factory.

The Research / Structure / Simulation agents call these tools on demand within
the loop to collect evidence, handing the power of "deciding what to query"
back to the LLM, and reducing the noise from naively stuffing the entire project
knowledge base into the prompt.

Tools fall into two categories by "query shape":
- relevance: search_nodes hits the top-K by semantics, suitable for "things
  related to X"
- enumeration: list_nodes lists the full roster by node_type, suitable for
  "what X are in the project"
Mismatching the two will miss things: answering an enumeration question with
search_nodes will surely miss low-relevance-score nodes.

All tools bind project_id through a closure, so the schema visible to the LLM
contains only business parameters; an agent node only needs to call
``make_project_tools(state.project_id)`` to get all read-only tools scoped to
the current project.
"""

from __future__ import annotations

import json

from langchain_core.tools import BaseTool, tool

from app.db.database import SessionLocal
from app.db.models import EdgeORM, NodeORM
from app.rag.retrieval import build_project_vector_context
from app.services.graph_mappers import db_fields_to_api
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


def _node_content_preview(node: NodeORM, limit: int = 120) -> str:
    text = (node.content or "").strip()
    fields = db_fields_to_api(node.meta)
    if fields:
        field_text = "; ".join(f"{k}: {v}" for k, v in list(fields.items())[:4])
        text = f"{text} | {field_text}".strip(" |")
    return text[:limit]


def make_project_tools(project_id: str, *, include_web_search: bool = True) -> list[BaseTool]:
    """Generate the read-only tool set bound to the given project.

    Internally maintains a turn-level search_cache, so when the LLM repeatedly
    calls search_nodes with variant queries within the same ReAct loop it hits
    existing results, avoiding repeated chroma calls.

    The cache key normalizes by "word set" (split on whitespace → sort → join
    back into a string), so the LLM hits the same cache whether it swaps word
    order ("Elara mentor" / "mentor Elara") or tweaks top_k; without
    normalization the LLM in ReAct can easily bypass the cache by rewriting
    keywords and hammer chroma.
    """
    search_cache: dict[str, str] = {}

    def _cache_key(query: str) -> str:
        # Word-order-independent + duplicate-word elimination + case-insensitive; top_k is not in the key, take max top_k to serve all callers
        tokens = sorted(set(query.strip().lower().split()))
        return " ".join(tokens)

    @tool
    def search_nodes(query: str, top_k: int = 5) -> str:
        """Semantically retrieve relevant nodes from the current project knowledge base (relevance query).

        Suitable for relevance-ranked questions like "things related to X /
        similar to Y / content mentioning Z". If the user asks an enumeration
        question like "what X are in the project", use list_nodes instead.

        Within this turn, once a similar keyword combination (word-order
        independent) has been called, sending the same set of words again hits
        the cache directly and does not call chroma; also do not deliberately
        bypass the cache and retry by swapping word order or changing top_k,
        there is no new information.

        Args:
            query: search keywords or a natural-language description.
            top_k: maximum number of nodes to return; 3-8 recommended.

        Returns:
            A JSON string list, each item with id / title / type /
            content_preview / score. On retriever error it returns an
            "[ERROR] ..." string, so the LLM wraps up immediately instead of
            retrying with different keywords.
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
                f"[ERROR] The retriever is temporarily unavailable: {err}. This "
                f"round, please answer directly based on the existing context, "
                f"and do not retry by calling search_nodes / list_nodes."
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
        """Enumerate all nodes in the current project, without semantic retrieval, with optional node_type filtering.

        Suitable for enumeration questions that require covering the full roster,
        like "what characters are in the project / what settings have been
        written / what plot nodes exist now"; do not answer such questions with
        search_nodes, otherwise nodes with low relevance to the query terms will
        be missed.

        Args:
            node_type: optional filter, one of six: character / worldbuilding /
                plot / idea / research / structure; an empty string or a value
                not in the whitelist means no filtering.
            limit: maximum number of nodes to return, default 100; for larger
                projects the LLM may reduce it to 30-50.

        Returns:
            A JSON string list, each item with id / title / type /
            content_preview.
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
                    "content_preview": _node_content_preview(n),
                }
                for n in nodes
            ],
            ensure_ascii=False,
        )

    @tool
    def get_node(node_id: str) -> str:
        """Read the full body and tags of the given node; return an empty object if not found.

        Args:
            node_id: node ID (obtained from search_nodes / list_nodes /
                list_neighbors).

        Returns:
            A JSON string with id / title / type / content / tags.
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
                "fields": db_fields_to_api(node.meta),
            },
            ensure_ascii=False,
        )

    @tool
    def list_neighbors(node_id: str) -> str:
        """List the directly connected one-hop neighbors of a node on the canvas.

        Returns only one hop; for multi-hop chained follow-ups like "the family
        of X's mentor", use multi_hop_neighbors instead, otherwise you would
        have to call this tool repeatedly and assemble the path yourself.

        Args:
            node_id: node ID.

        Returns:
            A JSON list, each item with id / title / type / direction /
            relation.
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

    @tool
    def multi_hop_neighbors(
        node_id: str, depth: int = 2, max_nodes: int = 20
    ) -> str:
        """Expand N-hop reachable nodes centered on node_id, with shortest relation-path backtracking.

        Suitable for chained relation Q&A ("the family of Elara's mentor" /
        "which nodes connect A and B"); for one-hop questions list_neighbors
        saves more tokens.

        The implementation runs a single BFS, completing in memory and
        returning; not cached within a turn (canvas relations change frequently,
        so the caching gain does not outweigh the invalidation cost).

        Args:
            node_id: starting node ID.
            depth: BFS hop count, 1-3 (default 2); over 3 is auto-truncated to
                prevent a result explosion.
            max_nodes: upper bound on returned nodes, default 20, hard cap 50;
                when exceeded, keep nodes closer to the start by ascending
                distance.

        Returns:
            A JSON list, each item with id / title / type / content_preview /
            distance / path; path looks like
            "start → [relation] → middle → [relation] → end". The start node
            itself is not in the results; returns "[]" if the start does not
            exist or does not belong to this project.
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

        # Bidirectional adjacency list; relation prefers label, falling back to relation_type when missing
        adjacency: dict[str, list[tuple[str, str]]] = {}
        for edge in edges:
            relation = edge.label or edge.relation_type or "related"
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
            """Backtrack from the end to the start, assembling a "start → [relation] → ... → end" string."""
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
        """Search the internet for external facts; only for "real-world reference" questions the project knowledge base can't answer.

        Typical uses:
        - Real-world research (medieval armor styles / real historical events / physics common sense / weapon names)
        - Real-time information (weather / news / facts around the current date)
        - Third-party knowledge (the specs of some external model / framework / library)

        Do not use for:
        - In-project plot / character / setting questions — use search_nodes / list_nodes instead
        - Asking about the agent itself (what model you use / what your name is) — this is system info, the web can't answer it

        Within this turn, the same keyword combination (order-independent) hits the cache; don't
        deliberately reword keywords to re-query, there's no new information.

        Args:
            query: Search keywords or a natural-language question.
            top_k: Maximum number of results to return, 3-6 recommended.

        Returns:
            A JSON string containing answer (a short answer synthesized by Tavily) and a hits list
            (each with title / url / snippet / score). When the web is unavailable, returns an
            "[ERROR] ..." string so the LLM wraps up immediately.
        """
        key = _cache_key(query)
        cached = search_cache.get(f"web::{key}")
        if cached is not None:
            return cached

        try:
            response = search_web(query, top_k)
        except WebSearchUnavailable as exc:
            error_payload = (
                f"[ERROR] {exc}. For this turn, answer based on the existing context and "
                f"project knowledge base; do not call web_search to retry."
            )
            search_cache[f"web::{key}"] = error_payload
            return error_payload
        except WebSearchError as exc:
            error_payload = f"[ERROR] web_search call failed: {exc}"
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

    tool_list = [
        search_nodes,
        list_nodes,
        get_node,
        list_neighbors,
        multi_hop_neighbors,
    ]
    if include_web_search:
        tool_list.append(web_search)
    return tool_list
