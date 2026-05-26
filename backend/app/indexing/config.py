"""向量索引配置常量。

本模块集中管理 ChromaDB collection 名称、embedding 维度和检索相关默认值。
路径配置来自 `app.core.paths`，开发态默认写入 `backend/data`，打包态跟随 Electron 指定目录。
"""

import os

from app.core.paths import BACKEND_ROOT, CHROMA_PATH


CHROMA_COLLECTION_NAME = "oc_lore_nodes"
DEFAULT_RELATION_LABEL = "关联"
DEFAULT_RELATION_TYPE = "relates_to"
DEFAULT_NODE_STATUS = "draft"


def _load_backend_env() -> None:
    """加载 backend/.env 中的本地配置。
    """
    env_path = BACKEND_ROOT / ".env"

    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip().lstrip("\ufeff")

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
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


def _get_bool_env(name: str, default: bool) -> bool:
    """读取布尔型环境变量，用于控制调试开关这类全局行为。"""
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


_load_backend_env()

# 加载向量模型配置
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
# 索引同步日志默认关闭，避免 Electron/uvicorn 控制台被增量同步细节刷屏；排查问题时在 .env 中改成 true。
INDEXING_DEBUG_LOG = _get_bool_env("OC_INDEXING_DEBUG_LOG", False)
MAX_TOP_K = 20
