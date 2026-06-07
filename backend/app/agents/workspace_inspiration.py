"""Lightweight workspace inspiration agent (second_revision change B / W5).

A standalone passive agent: [not part of the main-chat StateGraph], and it does
[not reuse ChatWorkspace's question_planner] (different responsibilities: the
latter actively drives progress, whereas this agent only responds passively when
the user sends a message).

Input: project id + user message + quoted node ids.
Output: a single WorkspaceInspirationOutput (type in search/rag/question/feedback
+ content), pushed to the frontend over SSE and dispatched by type to different
cards in the right column.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import load_prompt
from app.agents.schemas import WorkspaceInspirationOutput
from app.db.database import SessionLocal
from app.db.models import NodeORM
from app.llm.factory import get_llm_provider


_SYSTEM_PROMPT = load_prompt("workspace_inspiration")


def _quoted_block(project_id: str, node_ids: list[str]) -> str:
    """Join the titles + content of quoted nodes into a prompt block; return a placeholder when there are no quotes."""
    if not node_ids:
        return "(no quoted nodes)"
    with SessionLocal() as db:
        lines: list[str] = []
        for node_id in node_ids:
            node = db.get(NodeORM, node_id)
            if node is None or node.project_id != project_id:
                continue
            content = (node.content or "").strip().replace("\n", " ")
            lines.append(f"- [{node.node_type}] {node.title}: {content[:160]}")
    return "\n".join(lines) or "(no valid quoted nodes)"


def generate_workspace_output(
    project_id: str,
    message: str,
    quoted_node_ids: list[str],
) -> WorkspaceInspirationOutput:
    """Synchronously generate one workspace inspiration output; fall back to an encouraging note when the LLM fails."""
    messages = [
        SystemMessage(_SYSTEM_PROMPT),
        HumanMessage(
            f"[Quoted nodes]\n{_quoted_block(project_id, quoted_node_ids)}\n\n"
            f"[User message]\n{message}"
        ),
    ]
    try:
        return get_llm_provider().structured(messages, WorkspaceInspirationOutput)
    except Exception:
        return WorkspaceInspirationOutput(
            reasoning="LLM unavailable, degraded feedback",
            type="feedback",
            content="Got it, I've noted that down. Feel free to keep developing this idea, or select the related nodes and send them to me together.",
        )
