"""检索上下文 token 压缩节点。

避免长项目把 prompt 顶爆 LLM 的窗口: 用 tiktoken 累加 merged_context 的
token 数, 超出 ``context_token_cap`` 后按当前顺序截断, 保留前面更相关的
条目。即便单条超额也至少保留首项, 防止全部裁空。
"""

from __future__ import annotations

from typing import Any

import tiktoken

from app.agents.state import AgentState
from app.core.settings import get_agent_settings
from app.schemas import RagMergedContextItem


# cl100k_base 是 GPT-3.5/4 / DeepSeek 等主流模型的事实标准编码; 直接用现成
# 编码避免每次按 model 名字解析, 也无需联网下载。
_encoder = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_encoder.encode(text))


def context_compress_node(state: AgentState) -> dict[str, Any]:
    items = state.get("merged_context") or []
    if not items:
        return {}

    cap = get_agent_settings().context_token_cap

    kept: list[RagMergedContextItem] = []
    total = 0
    for item in items:
        cost = _count_tokens(f"{item.title}\n{item.content}")
        if total + cost > cap and kept:
            break
        kept.append(item)
        total += cost

    return {"merged_context": kept}