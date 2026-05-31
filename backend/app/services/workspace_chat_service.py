"""工作台底部对话框的 SSE 流（second_revision 改点 B / W5）。

把被动灵感 agent 的单条输出包成 SSE 事件推给前端右栏。LLM 调用是同步阻塞的，
放到线程里跑，避免卡住事件循环（与 chat_stream 的处理一致）。
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
    """产出一条工作台灵感卡片事件 + done。"""
    try:
        output = await asyncio.to_thread(
            generate_workspace_output, project_id, message, quoted_node_ids
        )
        yield _sse(
            {"type": "output", "output_type": output.type, "content": output.content}
        )
    except Exception:  # noqa: BLE001
        yield _sse({"type": "error", "message": "工作台灵感生成失败, 请再试一次"})
    yield _sse({"type": "done"})
