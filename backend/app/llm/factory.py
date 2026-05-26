"""LLM provider 单例工厂。

模块导入时不立刻构造 provider, 由调用方按需触发, 避免启动期未配置 .env 时
fail-fast 导致整个后端启动不来。``lru_cache`` 让同一进程内只构造一次, 测试
代码可以调用 ``get_llm_provider.cache_clear()`` 重置。
"""

from __future__ import annotations

from functools import lru_cache

from app.core.settings import get_llm_settings
from app.llm.provider import LlmProvider, MockProvider, OpenAICompatibleProvider


@lru_cache(maxsize=1)
def get_llm_provider() -> LlmProvider:
    settings = get_llm_settings()

    if settings.provider == "mock":
        return MockProvider()

    if settings.provider == "openai":
        return OpenAICompatibleProvider(settings)

    raise ValueError(
        f"未识别的 OC_LLM_PROVIDER: {settings.provider!r}; 仅支持 'openai' | 'mock'"
    )