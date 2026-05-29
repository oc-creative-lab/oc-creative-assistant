"""Web Search 客户端 (Tavily).

设计要点:
- 走 Tavily 的 ``include_answer=advanced`` 模式: 一次 HTTP 拿到"模型友好的
  简短答案 + 来源 list", 不需要 LLM 二次合成, 大幅省 token。
- 未配置 api_key 时不报错, 返回 ``WebSearchUnavailable``, 让上层工具走降级
  路径 (告诉 LLM"web 暂不可用, 请用已有信息作答")。
- 错误分类: 网络 / 鉴权 / 配额 全部归一成 ``WebSearchError`` 子类, 上层只
  根据"可不可重试"决定要不要继续打。
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.core.settings import get_web_search_settings


_TAVILY_ENDPOINT = "https://api.tavily.com/search"


@dataclass(frozen=True)
class WebSearchHit:
    """单条搜索结果, 字段对齐 search_nodes 风格, 让 LLM 习惯一致。"""

    title: str
    url: str
    snippet: str
    score: float


@dataclass(frozen=True)
class WebSearchResponse:
    """成功响应: ``answer`` 是 Tavily 直接合成的短答案, ``hits`` 是原始命中。"""

    answer: str
    hits: list[WebSearchHit]


class WebSearchError(RuntimeError):
    """所有可恢复 web 错误的基类; 文案直接给 LLM 看。"""


class WebSearchUnavailable(WebSearchError):
    """API key 未配置或服务整体不可用; LLM 收到后应立即收口, 不再重试。"""


def search_web(query: str, top_k: int = 5) -> WebSearchResponse:
    """调 Tavily 一次, 返回归一化后的结果。

    Args:
        query: 检索关键词或自然语言问句。
        top_k: 返回最多结果数, 自动 clamp 到 [1, 10]。

    Raises:
        WebSearchUnavailable: api_key 未配置 / Tavily 返回 401 或 429。
        WebSearchError: 其它网络或解析错误。
    """
    settings = get_web_search_settings()
    if not settings.is_configured:
        raise WebSearchUnavailable("web_search 未配置 API key, 暂不可用")

    bounded_top_k = max(1, min(int(top_k), 10))
    payload = {
        "api_key": settings.api_key,
        "query": query,
        "search_depth": "basic",
        "include_answer": "advanced",
        "max_results": bounded_top_k,
    }

    try:
        with httpx.Client(timeout=settings.timeout_seconds) as client:
            response = client.post(_TAVILY_ENDPOINT, json=payload)
    except httpx.HTTPError as exc:
        raise WebSearchError(f"web_search 网络异常: {exc}") from exc

    if response.status_code in (401, 403):
        raise WebSearchUnavailable("web_search 鉴权失败, 检查 OC_WEB_SEARCH_API_KEY")
    if response.status_code == 429:
        raise WebSearchUnavailable("web_search 触发配额限制, 本轮请用现有信息作答")
    if response.status_code >= 400:
        raise WebSearchError(f"web_search HTTP {response.status_code}: {response.text[:200]}")

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise WebSearchError("web_search 返回非法 JSON") from exc

    hits = [
        WebSearchHit(
            title=str(item.get("title", "")),
            url=str(item.get("url", "")),
            snippet=str(item.get("content", ""))[:400],
            score=float(item.get("score") or 0.0),
        )
        for item in (data.get("results") or [])
    ]
    return WebSearchResponse(
        answer=str(data.get("answer", "")).strip(),
        hits=hits,
    )