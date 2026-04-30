"""向量索引配置常量。

本模块集中管理 ChromaDB collection 名称、embedding 维度和检索相关默认值。
路径配置来自 `app.core.paths`，确保源码迁入 `app/` 后仍写入 `backend/data`。
"""

import os

from app.core.paths import BACKEND_ROOT, CHROMA_PATH


CHROMA_COLLECTION_NAME = "oc_lore_nodes"
DEFAULT_RELATION_LABEL = "关联"
DEFAULT_RELATION_TYPE = "relates_to"
DEFAULT_NODE_STATUS = "draft"


def _load_backend_env() -> None:
    """加载 backend/.env 中的本地配置。

    PoC 阶段不额外引入 python-dotenv；这里只支持常见的 KEY=VALUE 写法。
    已存在的系统环境变量优先级更高，便于部署或命令行临时覆盖。
    """
    env_path = BACKEND_ROOT / ".env"

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")

        if key:
            os.environ.setdefault(key, value)


def _get_int_env(name: str, default: int) -> int:
    """读取整数环境变量；配置非法时回退默认值，避免后端启动阶段直接崩溃。"""
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        return default


_load_backend_env()

# DashScope 兼容 OpenAI SDK，因此保留 base_url / api key / model / dimension 给 .env 或系统环境变量控制。
EMBEDDING_BASE_URL = os.getenv(
    "OC_EMBEDDING_BASE_URL",
    os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
)
EMBEDDING_API_KEY = os.getenv("OC_EMBEDDING_API_KEY", os.getenv("DASHSCOPE_API_KEY", ""))
EMBEDDING_MODEL = os.getenv("OC_EMBEDDING_MODEL", os.getenv("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v4"))
EMBEDDING_DIMENSION = _get_int_env(
    "OC_EMBEDDING_DIMENSION",
    _get_int_env("DASHSCOPE_EMBEDDING_DIMENSION", 1024),
)
MAX_TOP_K = 20
