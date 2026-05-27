"""LLM 调用的 Strategy Pattern 入口。

把 LangChain / OpenAI SDK 的细节封在 Provider 内, agent 节点只看到统一的
``chat`` (字符串) 与 ``structured`` (Pydantic) 两个方法, 屏蔽底层协议差异。

DeepSeek / 通义等 OpenAI 兼容服务普遍不支持 ``response_format=json_schema``,
真实 provider 显式固定 ``method="function_calling"`` 走 tool calls 协议,
兼容性最广。Mock provider 完全脱离网络, 按 schema 名字返回登记好的样本,
方便离线开发与 CI。
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any, Protocol, TypeVar

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.settings import LlmSettings


logger = logging.getLogger(__name__)

TSchema = TypeVar("TSchema", bound=BaseModel)


class LlmProvider(Protocol):
    """LLM 调用的统一接口契约。

    所有 agent 节点都通过本协议的实现来访问模型, Strategy Pattern 让 mock 与
    真实 provider 可在 .env 中无缝切换, 不需要改业务代码。
    """

    def chat(self, messages: list[BaseMessage]) -> str: ...

    def chat_stream(self, messages: list[BaseMessage]) -> Iterator[str]: ...

    def structured(
        self,
        messages: list[BaseMessage],
        schema: type[TSchema],
    ) -> TSchema: ...

    def chat_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[BaseTool],
    ) -> AIMessage: ...


class OpenAICompatibleProvider:
    """通过 OpenAI 兼容协议调用 DeepSeek / 通义 / OpenAI 官方等服务。

    底层使用 LangChain 的 ``ChatOpenAI``, 后续接 ToolNode / Checkpointer 时可以
    直接复用 LangChain 生态, 不必自己手写工具调用循环。
    """

    def __init__(self, settings: LlmSettings) -> None:
        if not settings.is_configured:
            raise ValueError("OC_LLM_* 配置缺失, 无法初始化 OpenAI 兼容 provider")

        self._client = ChatOpenAI(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
            temperature=0.3,
        )

    def chat(self, messages: list[BaseMessage]) -> str:
        response = self._client.invoke(messages)
        content = response.content if isinstance(response, AIMessage) else response
        return content if isinstance(content, str) else str(content)

    def chat_stream(self, messages: list[BaseMessage]) -> Iterator[str]:
        """逐 chunk yield 文本 delta; LangChain ChatOpenAI 原生 .stream() 支持。

        空 chunk (例如 LLM 还在思考还没产 token) 直接跳过, 让上层只看到
        真有内容的 token, 避免把 None / "" 灌进字符串累加。
        """
        for chunk in self._client.stream(messages):
            content = chunk.content if isinstance(chunk, AIMessage) else chunk
            if isinstance(content, str) and content:
                yield content

    def structured(
        self,
        messages: list[BaseMessage],
        schema: type[TSchema],
    ) -> TSchema:
        runnable = self._client.with_structured_output(schema, method="function_calling")
        return runnable.invoke(messages)

    def chat_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[BaseTool],
    ) -> AIMessage:
        """绑定工具调一次 LLM, 返回原生 AIMessage 让 tool_loop 解析 tool_calls。"""
        bound = self._client.bind_tools(tools)
        response = bound.invoke(messages)
        if isinstance(response, AIMessage):
            return response
        return AIMessage(content=str(getattr(response, "content", response)))

_MOCK_SAMPLES: dict[str, dict[str, Any]] = {
    "IntentClassification": {
        "intent": "inspiration",
        "confidence": 0.85,
        "reasoning": "用户希望探索创作方向, 命中 inspiration 意图。",
    },
    "InspirationOutput": {
        "reasoning": "围绕已有矮人铁匠设定补充背景冲突, 让角色更立体。",
        "suggestions": [
            "为铁匠设计一段被族长流放的过往",
            "引入一名挑战她技艺的年轻学徒",
            "让她持有一件揭示先祖秘密的器物",
        ],
        "referenced_node_ids": [],
        "proposed_changes": [
            {
                "change_type": "create_node",
                "target_id": None,
                "pending_id": "pending-1",
                "payload": {
                    "title": "暮岩",
                    "content": "年轻矮人学徒, 师从主角, 暗中怀疑师父的过往",
                    "node_type": "character",
                },
                "reason": "为主角引入冲突线",
            }
        ],
    },
    "ResearchOutput": {
        "reasoning": "在已有 graph 中按主题汇总相关角色与世界观片段。",
        "summary": "[mock] 该角色与现有族群存在历史纠葛, 核心冲突源自身份认同。",
        "referenced_node_ids": [],
        "proposed_changes": [],
    },
    "StructureOutput": {
        "reasoning": "用户已选定的角色尚未与情节连接, 补一条交互线。",
        "summary": "建议新增一条角色与族长之间的对抗交互线。",
        "proposed_changes": [],
    },
    "SimulationOutput": {
        "reasoning": "针对用户假设展开多条走向, 评估对现有节点的影响。",
        "branches": [
            {
                "scenario": "她接受任务但留下后路",
                "likelihood": "high",
                "downstream_impacts": ["部族暂时和解", "学徒身份成谜"],
                "affected_node_ids": [],
            }
        ],
    },
    "ChatAssemblerOutput": {
        "reply_text": "[mock] 围绕铁匠的故事, 给你几个方向: 流放过往、年轻学徒、先祖器物。",
        "cited_node_ids": [],
        "staging_summary": "我准备帮你新增 1 处, 等你确认。",
    },
    "ChatMetadataOutput": {
        "cited_node_ids": [],
        "staging_summary": "我准备帮你新增 1 处, 等你确认。",
    },
        "SummaryOutput": {
        "summary": "[mock] 用户与 agent 围绕主角的过往与族群冲突展开了多轮探讨, 已就主线方向达成基本共识。",
        "key_facts": [
            "主角是矮人铁匠, 身世存疑",
            "用户倾向于让冲突来自族群内部",
        ],
    },
}


class MockProvider:
    """离线确定性桩, 不发出任何网络请求。

    根据目标 schema 名字返回 ``_MOCK_SAMPLES`` 里登记的样本, 让前端联调与单测
    可以脱离 LLM。遇到未注册 schema 直接抛错, 暴露遗漏比静默返回 None 更安全。
    """

    def chat(self, messages: list[BaseMessage]) -> str:
        last_user = next(
            (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
            "",
        )
        text = last_user if isinstance(last_user, str) else str(last_user)
        return f"[mock] received: {text[:60]}"

    def chat_stream(self, messages: list[BaseMessage]) -> Iterator[str]:
        """按字符切分模拟 token stream, 让 mock 模式也能验证前端渐进渲染。"""
        for ch in self.chat(messages):
            yield ch

    def structured(
        self,
        messages: list[BaseMessage],
        schema: type[TSchema],
    ) -> TSchema:
        sample = _MOCK_SAMPLES.get(schema.__name__)
        if sample is None:
            raise ValueError(
                f"MockProvider 缺少 {schema.__name__} 样本; 请在 _MOCK_SAMPLES 注册"
            )
        return schema.model_validate(sample)

    def chat_with_tools(
        self,
        messages: list[BaseMessage],
        tools: list[BaseTool],
    ) -> AIMessage:
        """Mock 模式跳过工具调用, 直接返回空回复让 tool_loop 立即退出。"""
        return AIMessage(content="")