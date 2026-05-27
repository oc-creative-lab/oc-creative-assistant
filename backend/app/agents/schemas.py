"""Agent 编排涉及的 Pydantic 数据契约。

集中放在这里让 LangGraph 各节点只依赖 ``app.agents.schemas`` 一个入口, 后续
若需要把 LLM 输出协议从 function_calling 切回 json_schema 也只是一处改动。

每个 agent 输出都强制带 ``reasoning`` 字段: 既是显式 CoT 的着陆点, 也方便用户
在 UI 上看到"它为什么这么建议", 与 staging 表的 ``reason`` 字段呼应。
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class _LlmStructuredOutput(BaseModel):
    """所有 agent 输出 schema 的基类。

    OpenAI 兼容服务(尤其 DeepSeek)的 function_calling 协议偶尔会把 list / dict
    类型的字段二次序列化成 JSON 字符串塞进 tool call 参数, 让 Pydantic 直接抛
    ``list_type`` 这类校验错误。这里在 ``mode='before'`` 阶段对顶层 dict 字段
    做一次轻量解析: 看起来像 JSON 数组或对象的字符串就尝试 ``json.loads``,
    解析失败保持原样交由后续校验环节定性。
    """

    @model_validator(mode="before")
    @classmethod
    def _coerce_stringified_json(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        for key, value in list(data.items()):
            if not isinstance(value, str):
                continue
            stripped = value.strip()
            looks_like_json = (
                (stripped.startswith("[") and stripped.endswith("]"))
                or (stripped.startswith("{") and stripped.endswith("}"))
            )
            if not looks_like_json:
                continue
            try:
                data[key] = json.loads(stripped)
            except json.JSONDecodeError:
                pass

        return data


IntentLiteral = Literal[
    "inspiration",
    "research",
    "structure",
    "simulation",
    "small_talk",
]
"""主导意图取值; small_talk 兜底所有不归入四种 agent 的闲聊。"""

ChangeTypeLiteral = Literal[
    "create_node",
    "create_edge",
    "update_node",
    "delete_node",
    "delete_edge",
]
"""staging 表支持的画布变更类型; delete 同样走 staging 用户确认, HITL 保证不会
   绕过用户直接删内容, 因此可以与 create / update 共用一条通道。"""

LikelihoodLiteral = Literal["high", "medium", "low"]


class IntentClassification(_LlmStructuredOutput):
    """intent_router 的结构化输出, 把用户消息归类到一个 agent 类型上。

    primary 决定 graph 路由到哪个 agent 节点, 也是装配器选择回复主线
    (语气、副作用归属) 的依据。confidence 留作前端调试与未来阈值控制用,
    暂不参与路由决策。
    """

    primary: IntentLiteral
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    reasoning: str = ""


class ProposedChange(_LlmStructuredOutput):
    """Agent 想做的画布变更, 进 staging 表等待用户确认。

    ``pending_id`` 给同一 batch 内的新节点分配临时占位 id, 让边可以引用尚未
    落库的新节点; 提交时再用真实 node_id 回填, 解决"先节点后边"的依赖问题。
    """

    change_type: ChangeTypeLiteral
    target_id: str | None = None
    pending_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class InspirationOutput(_LlmStructuredOutput):
    """灵感发散 agent 输出, 重点是开放式建议, 不强制写画布。"""

    reasoning: str
    suggestions: list[str] = Field(default_factory=list)
    referenced_node_ids: list[str] = Field(default_factory=list)
    proposed_changes: list[ProposedChange] = Field(default_factory=list)


class ResearchOutput(_LlmStructuredOutput):
    """研究 / 检索 agent 输出, 必须带引用, 默认不写画布。"""

    reasoning: str
    summary: str
    referenced_node_ids: list[str] = Field(default_factory=list)
    proposed_changes: list[ProposedChange] = Field(default_factory=list)


class StructureOutput(_LlmStructuredOutput):
    """结构化 agent 输出, 主要用于产出新节点和新关系。

    与 InspirationOutput / ResearchOutput 保持同一组字段, 让 chat_assembler
    在装配 cited_node_ids 时不区分 intent 即可统一处理。
    """

    reasoning: str
    summary: str
    referenced_node_ids: list[str] = Field(default_factory=list)
    proposed_changes: list[ProposedChange] = Field(default_factory=list)


class SimulationBranch(_LlmStructuredOutput):
    """单条假设走向。"""

    scenario: str
    likelihood: LikelihoodLiteral
    downstream_impacts: list[str] = Field(default_factory=list)
    affected_node_ids: list[str] = Field(default_factory=list)


class SimulationOutput(_LlmStructuredOutput):
    """假设推演 agent 输出, 列出多条走向供用户选择, 永不写画布。"""

    reasoning: str
    branches: list[SimulationBranch] = Field(default_factory=list)


class ChatAssemblerOutput(_LlmStructuredOutput):
    """对话装配器输出, 把结构化 agent 结果转成自然语言气泡。

    ``staging_summary`` 是可选的一行摘要, 渲染在气泡尾部告诉用户"我准备改 N 处",
    与 staging 面板形成上下呼应。
    """

    reply_text: str
    cited_node_ids: list[str] = Field(default_factory=list)
    staging_summary: str = ""


class SummaryOutput(_LlmStructuredOutput):
    """摘要压缩节点的结构化输出。

    ``key_facts`` 让 LLM 显式列出"本段对话锁定的关键事实", 既保证压缩不漏点,
    也方便上层在调试或 UI 提示里抓"这次摘要保住了哪些信息"。
    """

    summary: str
    key_facts: list[str] = Field(default_factory=list)