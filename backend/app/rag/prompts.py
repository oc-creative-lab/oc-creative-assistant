"""RAG prompt templates and context formatting.

This module is only responsible for assembling the already-filtered graph/vector
context into a prompt for Agent preview. It does not read the database, nor does it
trigger any real LLM call.
"""

from __future__ import annotations

from app.schemas import RagCurrentNodePayload, RagGraphContextItem, RagVectorContextItem


def build_inspiration_prompt(
    current_node: RagCurrentNodePayload,
    graph_context: list[RagGraphContextItem],
    vector_context: list[RagVectorContextItem],
    user_query: str,
) -> str:
    """Build the prompt for the Idea-guidance Agent.

    Args:
        current_node: The node currently requesting AI assistance.
        graph_context: One-hop relation context extracted from the canvas edges.
        vector_context: Semantically related nodes retrieved from the vector index.
        user_query: The retrieval question entered by the user or generated as a
            fallback by the service layer.

    Returns:
        The prompt text for frontend preview; this function does not call the LLM.
    """
    graph_context_text = _format_graph_context(graph_context)
    vector_context_text = _format_vector_context(vector_context)

    return f"""You are the "Idea-guidance Agent" in OC Creative Assistant.

Your task is to help original-character creators think, not to write the actual content for the user.

You may only output:
1. Guiding questions;
2. Suggestions for supplementing settings;
3. New nodes that may need to be created;
4. Reminders about potential conflicts with existing settings.

You may not output:
1. Complete novel passages;
2. Complete plot prose;
3. Final settings decided on the user's behalf;
4. Direct continuation of the user's work.

Please answer strictly based on the project context provided below.

---

[Current Node]

Node type: {current_node.type}
Node title: {current_node.title}
Node content:
{current_node.content}

---

[Canvas Relation Context]

The following comes from node connections the user manually created on the canvas, and has higher priority:

{graph_context_text}

---

[Vector Retrieval Context]

The following comes from RAG semantic retrieval and may be related to the current node:

{vector_context_text}

---

[User Request]

{user_query}

---

[Output Requirements]

Please output JSON. Do not output Markdown, and do not output complete plot prose.

The JSON format is as follows:

{{
  "agent": "inspiration",
  "summary": "A one-sentence summary of the creative state of the current node",
  "questions": [
    "Guiding question 1",
    "Guiding question 2",
    "Guiding question 3"
  ],
  "missing_parts": [
    "Missing setting point 1",
    "Missing setting point 2"
  ],
  "suggested_nodes": [
    {{
      "nodeType": "plot",
      "title": "Suggested new node title",
      "reason": "Why this node is suggested"
    }}
  ],
  "boundary_notice": "Remind the user that these are only suggestions and that the final settings are decided by the user"
}}"""


def _format_graph_context(context: list[RagGraphContextItem]) -> str:
    """Format the graph relation context.

    Args:
        context: The filtered one-hop graph relation context.

    Returns:
        The graph relation context fragment for the prompt.
    """
    if not context:
        # Explicitly writing "none" helps the downstream LLM understand the context gap better than an empty string.
        return "No directly connected related nodes"

    return "\n\n".join(
        [
            f"- Relation: {item.relation_label} ({item.relation_type}, {item.direction})\n"
            f"  Node type: {item.type}\n"
            f"  Node title: {item.title}\n"
            f"  Node content: {item.content}"
            for item in context
        ]
    )


def _format_vector_context(context: list[RagVectorContextItem]) -> str:
    """Format the vector retrieval context.

    Args:
        context: The filtered vector retrieval results.

    Returns:
        The vector retrieval context fragment for the prompt.
    """
    if not context:
        # Keep a placeholder paragraph even with no results, to make it easier for the frontend to debug the prompt structure.
        return "No vector retrieval results"

    return "\n\n".join(
        [
            f"- Similarity: {item.score:.2f}\n"
            f"  Node type: {item.type}\n"
            f"  Node title: {item.title}\n"
            f"  Node content: {item.content}"
            for item in context
        ]
    )
