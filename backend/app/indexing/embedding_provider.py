"""真实 Embedding Provider 实现。

通过 OpenAI 兼容协议调用阿里云 DashScope 的 embedding 服务。失败时调用方
负责降级到本地 hash provider,保证 RAG 流程不被网络波动击穿。
"""

from __future__ import annotations

import logging

from openai import OpenAI

from app.core.settings import EmbeddingSettings


logger = logging.getLogger(__name__)


class DashScopeEmbeddingProvider:
    """调用 DashScope text-embedding-v4 的 embedding 提供者。"""

    def __init__(self, settings: EmbeddingSettings) -> None:
        if not settings.is_configured:
            raise ValueError("DashScope embedding 配置缺失,请检查 .env 中的 OC_EMBEDDING_* 变量")

        self._client = OpenAI(base_url=settings.base_url, api_key=settings.api_key)
        self._model = settings.model
        self.dimension = settings.dimension

    def embed(self, text: str) -> list[float]:
        """将文本转成向量。

        Args:
            text: 待向量化的文本;为空时返回全零向量,与 hash provider 行为一致。

        Returns:
            模型输出的向量(长度 = self.dimension)。
        """
        cleaned = text.strip()
        if not cleaned:
            return [0.0] * self.dimension

        response = self._client.embeddings.create(
            model=self._model,
            input=cleaned,
            dimensions=self.dimension,
        )
        return list(response.data[0].embedding)