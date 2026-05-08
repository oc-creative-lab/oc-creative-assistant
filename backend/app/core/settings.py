"""应用运行时配置。

集中读取 .env / 环境变量,避免业务模块直接依赖 os.getenv,便于未来切换
pydantic-settings 或注入测试配置。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app.core.paths import BACKEND_ROOT


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
    """对话 LLM 服务配置。"""

    base_url: str | None
    api_key: str | None
    model: str

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)


def get_llm_settings() -> LlmSettings:
    return LlmSettings(
        base_url=os.getenv("OC_LLM_BASE_URL"),
        api_key=os.getenv("OC_LLM_API_KEY"),
        model=os.getenv("OC_LLM_MODEL", "deepseek-chat"),
    )