"""SSE 流式 chat 实现。

LangGraph 的 sync 接口 `graph.stream` 跟项目现用的 `SqliteSaver` (同步
checkpointer) 兼容; 直接调 `graph.astream` 会强制走 `aget_tuple`, 要求
`AsyncSqliteSaver` + `aiosqlite`, 与现有架构不匹配。

折中: 在 `asyncio.to_thread` 里跑同步 `graph.stream`, 通过 `asyncio.Queue`
桥接成 async generator, 既不引入 aiosqlite 依赖, 也不必把 chat_service.
run_chat_turn 整体改成 async。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.agents.graph import get_agent_graph
from app.db.database import SessionLocal
from app.schemas import ChatRequest
from app.services.chat_service import require_session


logger = logging.getLogger(__name__)


_NODE_LABELS: dict[str, str] = {
    "load_context": "加载上下文",
    "intent_router": "判断意图",
    "parallel_retrieval": "检索知识库",
    "context_compress": "压缩上下文",
    "inspiration_agent": "灵感发散中",
    "research_agent": "考据查证中",
    "structure_agent": "整理结构中",
    "simulation_agent": "推演分支中",
    "boundary_check": "边界校验",
    "chat_assembler": "生成回复",
    "persistence_hub": "持久化结果",
    "summary_compress": "压缩对话摘要",
}


_DONE = object()


def _sse(data: dict[str, Any]) -> str:
    """字典 -> SSE 协议 data 行 (双 \\n 分隔事件)。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_events(node_name: str, node_output: Any) -> list[dict[str, Any]]:
    """节点输出 -> SSE 事件列表 (主事件 + 关键节点附带元数据事件)。"""
    events: list[dict[str, Any]] = [
        {
            "type": "node_end",
            "node": node_name,
            "label": _NODE_LABELS.get(node_name, node_name),
        }
    ]

    if not isinstance(node_output, dict):
        return events

    if node_name == "intent_router":
        intent = node_output.get("intent")
        if intent is not None:
            events.append({
                "type": "intent",
                "primary": intent.primary,
                "confidence": intent.confidence,
            })

    elif node_name == "chat_assembler":
        assembler = node_output.get("assembler_output")
        if assembler is not None:
            events.append({
                "type": "reply_ready",
                "reply_text": assembler.reply_text,
                "cited_node_ids": list(assembler.cited_node_ids),
                "staging_summary": assembler.staging_summary,
            })

    elif node_name == "persistence_hub":
        events.append({
            "type": "persistence_done",
            "message_id": node_output.get("assistant_message_id", ""),
            "batch_id": node_output.get("staging_batch_id"),
            "staging_count": node_output.get("staging_count", 0),
        })

    return events


async def stream_chat_turn(payload: ChatRequest) -> AsyncIterator[str]:
    """跑 graph.stream (sync) 并把每个节点输出转 SSE 事件。

    任何 graph 内部异常都收敛成一条 error 事件, 让前端能优雅切兜底文案,
    不会撞 stream 中途截断。
    """
    with SessionLocal() as db:
        session = require_session(db, payload.session_id)
        thread_id = session.thread_id
        project_id = session.project_id

    graph = get_agent_graph()
    config = {"configurable": {"thread_id": thread_id}}
    inputs = {
        "session_id": payload.session_id,
        "project_id": project_id,
        "user_message": payload.user_message,
        "selected_node_ids": list(payload.selected_node_ids),
    }

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def producer() -> None:
        """同步线程跑 graph.stream, call_soon_threadsafe 把 chunk 投递回 loop。

        多 stream_mode 时 LangGraph 把每个 chunk 包成 (mode, payload) 二元组,
        主协程根据 mode 分发: "updates" 是节点级更新, "custom" 是节点内通过
        get_stream_writer 推的 token 事件。
        """
        try:
            stream = graph.stream(
                inputs, config=config, stream_mode=["updates", "custom"]
            )
            for chunk in stream:
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _DONE)

    producer_task = asyncio.create_task(asyncio.to_thread(producer))

    try:
        while True:
            item = await queue.get()
            if item is _DONE:
                break
            if isinstance(item, Exception):
                logger.exception("stream_chat_turn graph 内部失败: %s", item)
                yield _sse({"type": "error", "message": "推理过程出错, 请再试一次"})
                return

            mode, payload = item
            if mode == "custom":
                # chat_assembler 通过 get_stream_writer 推的 token 事件, 透传给前端
                if isinstance(payload, dict) and payload.get("type"):
                    yield _sse(payload)
                continue

            # mode == "updates": payload 是 {node_name: node_output} 字典
            for node_name, node_output in payload.items():
                for event in _build_events(node_name, node_output):
                    yield _sse(event)

        yield _sse({"type": "done"})

    except Exception as exc:  # noqa: BLE001
        logger.exception("stream_chat_turn 失败: %s", exc)
        yield _sse({"type": "error", "message": "推理过程出错, 请再试一次"})
    finally:
        await producer_task