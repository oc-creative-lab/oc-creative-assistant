"""Application runtime configuration.

Centralizes reading of .env / environment variables, avoiding having business
modules depend directly on os.getenv, making it easier to switch to
pydantic-settings or inject test configuration in the future.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app.core.paths import BACKEND_ROOT, DATA_DIR


def _load_env() -> None:
    """Load backend/.env into the current process's environment variables.

    Runs only once at module import; silently skips when .env does not exist, so
    that environments without a .env (such as CI) can still start up (falling back
    to placeholder embeddings in that case).
    """
    env_path: Path = BACKEND_ROOT / ".env"
    load_dotenv(env_path, override=False)


_load_env()


def _get_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable, treating 1/true/yes as True."""
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
    """Embedding service configuration."""

    base_url: str | None
    api_key: str | None
    model: str
    dimension: int

    @property
    def is_configured(self) -> bool:
        """Determine whether the minimum configuration to call a real embedding service is present."""
        return bool(self.base_url and self.api_key and self.model)


@dataclass(frozen=True)
class IndexingSettings:
    """Index debugging-related switches."""

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
    """Chat LLM service configuration.

    ``provider`` determines the Strategy Pattern implementation choice: ``openai``
    uses a real OpenAI-compatible protocol (DeepSeek/Tongyi/official OpenAI),
    ``mock`` uses a local deterministic stub for offline development and unit tests.
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
    """Web search tool configuration.

    When api_key is left empty, the ``web_search`` tool directly returns a
    degraded notice instead of erroring, ensuring offline development and CI/unit
    tests without a configured key can still run the entire Agent pipeline.
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
    """Agent graph runtime configuration.

    ``checkpointer_db_path`` provides the persistence path for LangGraph's
    SqliteSaver, kept separate from the business SQLite to avoid transaction
    conflicts; ``context_token_cap`` controls the upper bound of retrieval context
    injected into the conversation each turn, preventing long projects from
    blowing the prompt past the LLM's window.

    Multi-layer memory related:
    - ``recent_message_window``: load_context takes the last N messages verbatim to feed the prompt
    - ``summary_keep_recent``: how many messages to keep out of the summary during summary compression
    - ``summary_compress_every``: how many more old messages must accumulate beyond the high-water mark before compression is triggered again
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


@dataclass(frozen=True)
class AppSettings:
    """Application-wide runtime switches."""

    dev_mode: bool


def get_app_settings() -> AppSettings:
    return AppSettings(dev_mode=_get_bool("OC_DEV_MODE", False))