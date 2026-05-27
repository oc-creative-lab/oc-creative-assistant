"""LangGraph 持久化 Checkpointer 单例。

把 AgentState 的中间快照写入独立的 sqlite 文件 (与业务库分离避免事务冲突);
模块导入时不立刻建连接, 由 ``build_graph`` 在编译时按需触发。

``check_same_thread=False`` 是 FastAPI 多线程下的必要参数: SQLite 默认禁止
跨线程共享连接, 关闭后由 SqliteSaver 自身的锁机制保证安全。
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache

from langgraph.checkpoint.sqlite import SqliteSaver

from app.core.settings import get_agent_settings


_ALLOWED_MSGPACK_MODULES: list[tuple[str, str]] = [
    ("app.agents.schemas", "IntentClassification"),
    ("app.agents.schemas", "InspirationOutput"),
    ("app.agents.schemas", "ResearchOutput"),
    ("app.agents.schemas", "StructureOutput"),
    ("app.agents.schemas", "SimulationOutput"),
    ("app.agents.schemas", "SimulationBranch"),
    ("app.agents.schemas", "ChatAssemblerOutput"),
    ("app.agents.schemas", "ProposedChange"),
    ("app.schemas", "RagCurrentNodePayload"),
    ("app.schemas", "RagGraphContextItem"),
    ("app.schemas", "RagVectorContextItem"),
    ("app.schemas", "RagMergedContextItem"),
]


@lru_cache(maxsize=1)
def get_checkpointer() -> SqliteSaver:
    """返回 LangGraph Checkpointer 单例。"""
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    settings = get_agent_settings()
    settings.checkpointer_db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        settings.checkpointer_db_path.as_posix(),
        check_same_thread=False,
    )
    serde = JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_MSGPACK_MODULES)
    return SqliteSaver(conn, serde=serde)