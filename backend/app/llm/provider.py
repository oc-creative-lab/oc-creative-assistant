"""LLM Strategy 抽象与具体实现。

通过统一 Provider 接口在 OpenAI 兼容协议下切换 DeepSeek / Qwen / OpenAI。
为离线开发与测试提供 MockProvider, 避免每次调试都消耗外部 API 配额, 同时
满足 proposal 7.3.1 的 multi-model hot-swap 缓解措施。
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from app.core.settings import LlmSettings, get_llm_settings

logger = logging.getLogger(__name__)


class LlmProvider(ABC):
    """LLM 调用抽象。

    业务层只关心传入 messages 与 response_schema, 具体协议、结构化输出兜底
    由实现类负责, 便于在不改业务代码的前提下切换模型。
    """

    name: str = "abstract"

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        response_schema: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        """同步调用 LLM。

        Args:
            messages: OpenAI 风格 chat messages。
            response_schema: 指定时强制 LangChain `with_structured_output` 校验。

        Returns:
            未指定 schema 时返回原始字符串; 指定时返回对应 Pydantic 实例。
        """


class OpenAICompatibleProvider(LlmProvider):
    """覆盖 OpenAI / DeepSeek / 阿里 Qwen 等 OpenAI-compatible endpoint。"""

    name = "openai_compatible"

    def __init__(self, settings: LlmSettings) -> None:
        """构造 LangChain ChatOpenAI client。

        Args:
            settings: 已校验过的 LLM 设置, 缺一不可。
        """
        if not settings.is_configured:
            raise ValueError("LLM 配置缺失, 请检查 .env 中的 OC_LLM_* 变量")

        # 延迟导入避免无 LLM 配置场景下也要装 langchain-openai。
        from langchain_openai import ChatOpenAI

        self._llm = ChatOpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
            temperature=0.7,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        response_schema: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        if response_schema is None:
            response = self._llm.invoke(messages)
            return response.content

        structured_llm = self._llm.with_structured_output(
            response_schema,
            method="function_calling",
        )
        return structured_llm.invoke(messages)


class MockProvider(LlmProvider):
    """离线占位 Provider。

    返回符合 schema 的占位实例, 便于在无网络或未配置 API key 的开发机上跑通
    LangGraph 链路, 也方便单元测试断言。
    """

    name = "mock"

    def chat(
        self,
        messages: list[dict[str, str]],
        response_schema: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        if response_schema is None:
            return "[mock] LLM 未配置, 返回占位文本。"

        return response_schema.model_validate(self._build_sample(response_schema))

    def _build_sample(self, schema: type[BaseModel]) -> dict[str, Any]:
        """按 schema 字段类型生成 mock 值, 容器全部留空, 字符串填占位标记。"""
        sample: dict[str, Any] = {}
        for field_name, field in schema.model_fields.items():
            sample[field_name] = self._sample_for_annotation(field.annotation)
        return sample

    def _sample_for_annotation(self, annotation: Any) -> Any:
        origin = getattr(annotation, "__origin__", None)
        if origin is list:
            return []
        if annotation is str:
            return "[mock]"
        if annotation is int:
            return 0
        return None


def get_llm_provider() -> LlmProvider:
    """根据 .env 选择 Provider。

    OC_LLM_MODE=mock 或 LLM 配置缺失时降级到 MockProvider, 保证 PoC 离线可跑。
    """
    if os.getenv("OC_LLM_MODE", "").strip().lower() == "mock":
        return MockProvider()

    settings = get_llm_settings()

    if not settings.is_configured:
        logger.warning("OC_LLM_* 未配置, 降级到 MockProvider")
        return MockProvider()

    try:
        return OpenAICompatibleProvider(settings)
    except Exception as error:  # noqa: BLE001
        # 初始化期间任何导入或配置异常都降级到 mock, 避免阻塞应用启动。
        logger.warning("OpenAICompatibleProvider 初始化失败, 降级 Mock: %s", error)
        return MockProvider()