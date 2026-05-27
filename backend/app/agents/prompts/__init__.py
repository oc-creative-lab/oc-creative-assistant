"""Prompt 加载器。

按 `name + version` 从 prompts 目录读取 .md 文件并 LRU 缓存; 让 prompt 与 Python
代码完全解耦, 改文本不用动逻辑, 也方便后续做版本灰度。

文件命名规范: ``{name}.{version}.md`` (例如 ``structure.v1.md``)。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


PROMPTS_DIR = Path(__file__).parent

DEFAULT_VERSIONS: dict[str, str] = {
    "structure": "v1",
    "inspiration": "v1",
    "research": "v1",
    "simulation": "v1",
    "intent_router": "v1",
    "chat_assembler": "v1",
    "chat_assembler_small_talk": "v1",
    "chat_assembler_reply": "v1",
    "chat_assembler_metadata": "v1",
    "summary_compress": "v1",
}
"""每个 prompt 当前生效版本, 灰度切换时改这里。"""


@lru_cache(maxsize=None)
def load_prompt(name: str, version: str | None = None) -> str:
    """读取并缓存 prompt 文本; 文件不存在直接抛 FileNotFoundError 让启动期就暴露。"""
    actual_version = version or DEFAULT_VERSIONS.get(name, "v1")
    path = PROMPTS_DIR / f"{name}.{actual_version}.md"
    return path.read_text(encoding="utf-8").strip()


def get_prompt_version(name: str) -> str:
    """供埋点 / 调试日志使用, 知道当前用的是哪版 prompt。"""
    return DEFAULT_VERSIONS.get(name, "v1")