"""应用运行时配置。

集中读取 .env / 环境变量,避免业务模块直接依赖 os.getenv,便于未来切换
pydantic-settings 或注入测试配置。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app.core.paths import BACKEND_ROOT, DATA_DIR


def _load_env() -> None:
    """加载 backend/.env 到当前进程环境变量。

    只在模块导入时执行一次;.env 不存在时静默跳过,保证 CI 等无 .env
    场景仍可启动(届时使用占位 embedding 降级)。
    """
    env_path: Path = BACKEND_ROOT / ".env"
    load_dotenv(env_path, override=False)


_load_env()


def _get_bool(name: str, default: bool = False) -> bool:
    """读取布尔环境变量,接受 1/true/yes 视为 True。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class EmbeddingSettings:
    """Embedding 服务配置。"""

    base_url: str | None
    api_key: str | None
    model: str
    dimension: int

    @property
    def is_configured(self) -> bool:
        """判断是否具备调用真实 embedding 服务的最低配置。"""
        return bool(self.base_url and self.api_key and self.model)


@dataclass(frozen=True)
class IndexingSettings:
    """索引调试相关开关。"""

    debug_log: bool


def get_embedding_settings() -> EmbeddingSettings:
    return EmbeddingSettings(
        base_url=os.getenv("OC_EMBEDDING_BASE_URL"),
        api_key=os.getenv("OC_EMBEDDING_API_KEY"),
        model=os.getenv("OC_EMBEDDING_MODEL", "text-embedding-v4"),
        dimension=_get_int("OC_EMBEDDING_DIMENSION", 1024),
    )


def get_indexing_settings() -> IndexingSettings:
    return IndexingSettings(debug_log=_get_bool("OC_INDEXING_DEBUG_LOG", False))


@dataclass(frozen=True)
class LlmSettings:
    """对话 LLM 服务配置。

    ``provider`` 决定 Strategy Pattern 的实现选择: ``openai`` 走真实 OpenAI 兼容
    协议(DeepSeek/通义/官方 OpenAI), ``mock`` 走本地确定性桩, 用于离线开发与单测。
    """

    provider: str
    base_url: str | None
    api_key: str | None
    model: str

    @property
    def is_configured(self) -> bool:
        if self.provider == "mock":
            return True
        return bool(self.base_url and self.api_key and self.model)


def get_llm_settings() -> LlmSettings:
    return LlmSettings(
        provider=os.getenv("OC_LLM_PROVIDER", "openai").strip().lower(),
        base_url=os.getenv("OC_LLM_BASE_URL"),
        api_key=os.getenv("OC_LLM_API_KEY"),
        model=os.getenv("OC_LLM_MODEL", "deepseek/deepseek-chat"),
    )


@dataclass(frozen=True)
class WebSearchSettings:
    """Web search 工具配置。

    api_key 留空时 ``web_search`` 工具直接返回降级提示而不报错, 保证离线开发
    和未配置 key 的 CI/单测仍能跑通整条 Agent 链路。
    """

    provider: str
    api_key: str | None
    timeout_seconds: int

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)


def get_web_search_settings() -> WebSearchSettings:
    return WebSearchSettings(
        provider=os.getenv("OC_WEB_SEARCH_PROVIDER", "tavily").strip().lower(),
        api_key=os.getenv("OC_WEB_SEARCH_API_KEY") or None,
        timeout_seconds=_get_int("OC_WEB_SEARCH_TIMEOUT", 10),
    )


@dataclass(frozen=True)
class AgentSettings:
    """Agent 图运行时配置。

    ``checkpointer_db_path`` 为 LangGraph 的 SqliteSaver 提供持久化路径, 与业务
    SQLite 分离避免事务冲突; ``context_token_cap`` 控制每轮注入对话的检索上下文
    上限, 防止长项目把 prompt 顶爆 LLM 的窗口。

    多层记忆相关:
    - ``recent_message_window``: load_context 取最近 N 条消息原文喂 prompt
    - ``summary_keep_recent``: 摘要压缩时保留多少条不进入 summary
    - ``summary_compress_every``: 高水位之外再积累多少条老消息才再次触发压缩
    """

    checkpointer_db_path: Path
    context_token_cap: int
    recent_message_window: int
    summary_keep_recent: int
    summary_compress_every: int


def get_agent_settings() -> AgentSettings:
    return AgentSettings(
        checkpointer_db_path=DATA_DIR / "langgraph_checkpoint.sqlite3",
        context_token_cap=_get_int("OC_AGENT_CONTEXT_TOKEN_CAP", 2000),
        recent_message_window=_get_int("OC_AGENT_RECENT_MESSAGE_WINDOW", 10),
        summary_keep_recent=_get_int("OC_AGENT_SUMMARY_KEEP_RECENT", 10),
        summary_compress_every=_get_int("OC_AGENT_SUMMARY_COMPRESS_EVERY", 6),
    )