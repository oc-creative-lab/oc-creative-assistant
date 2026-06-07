"""SSE stream for the workspace's bottom chat box (second_revision change B / W5).

Wraps a single output from the passive inspiration agent into an SSE event and
pushes it to the frontend's right panel. The LLM call is synchronous and blocking,
so it is run in a thread to avoid blocking the event loop (consistent with how
chat_stream handles it).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from app.agents.workspace_inspiration import generate_workspace_output


def _sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_workspace_chat(
    project_id: str,
    message: str,
    quoted_node_ids: list[str],
) -> AsyncIterator[str]:
    """Emit one workspace inspiration card event + done."""
    try:
        output = await asyncio.to_thread(
            generate_workspace_output, project_id, message, quoted_node_ids
        )
        yield _sse(
            {"type": "output", "output_type": output.type, "content": output.content}
        )
    except Exception:  # noqa: BLE001
        yield _sse({"type": "error", "message": "Workspace inspiration generation failed, please try again"})
    yield _sse({"type": "done"})
