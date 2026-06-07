"""Prompt loader.

Reads .md files from the prompts directory by `name + version` with an LRU cache;
fully decouples prompts from the Python code, so changing text needs no logic
changes and makes future versioned rollouts easy.

File naming convention: ``{name}.{version}.md`` (e.g. ``structure.v1.md``).
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
"""The currently active version of each prompt; change here for staged rollouts."""


@lru_cache(maxsize=None)
def load_prompt(name: str, version: str | None = None) -> str:
    """Read and cache prompt text; a missing file raises FileNotFoundError directly so it surfaces at startup."""
    actual_version = version or DEFAULT_VERSIONS.get(name, "v1")
    path = PROMPTS_DIR / f"{name}.{actual_version}.md"
    return path.read_text(encoding="utf-8").strip()


def get_prompt_version(name: str) -> str:
    """For instrumentation / debug logs, to know which prompt version is in use."""
    return DEFAULT_VERSIONS.get(name, "v1")
