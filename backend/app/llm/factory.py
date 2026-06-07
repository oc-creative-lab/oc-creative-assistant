"""LLM provider singleton factory.

The provider is not constructed at import time; the caller triggers it on demand,
so a missing .env at startup won't fail-fast and take down the whole backend.
``lru_cache`` ensures it's constructed only once per process, and test code can
call ``get_llm_provider.cache_clear()`` to reset it.
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
        f"Unrecognized OC_LLM_PROVIDER: {settings.provider!r}; only 'openai' | 'mock' are supported"
    )