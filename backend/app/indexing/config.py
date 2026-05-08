"""向量索引配置常量。

本模块集中管理 ChromaDB collection 名称、embedding 维度和检索相关默认值。
路径配置来自 `app.core.paths`，开发态默认写入 `backend/data`，打包态跟随 Electron 指定目录。
embedding 与索引调试相关的运行时配置统一从 `app.core.settings` 读取，避免
.env 解析散落在多个模块里。
"""

from app.core.paths import CHROMA_PATH
from app.core.settings import get_embedding_settings, get_indexing_settings


COLLECTION_BY_NODE_TYPE: dict[str, str] = {
    "character": "oc_characters",
    "worldbuilding": "oc_worldbuilding",
    "plot": "oc_plot",
}
DEFAULT_COLLECTION_NAME = "oc_misc"
DEFAULT_RELATION_LABEL = "关联"
DEFAULT_RELATION_TYPE = "relates_to"
DEFAULT_NODE_STATUS = "draft"

# Embedding/索引配置在模块导入时一次性快照，避免热路径反复读取 .env。
_embedding_settings = get_embedding_settings()
_indexing_settings = get_indexing_settings()

# 这些常量同时被 vector_store/sync 使用，保留模块级别名以兼容现有 import 路径。
EMBEDDING_BASE_URL = _embedding_settings.base_url or ""
EMBEDDING_API_KEY = _embedding_settings.api_key or ""
EMBEDDING_MODEL = _embedding_settings.model
EMBEDDING_DIMENSION = _embedding_settings.dimension

# 索引同步日志默认关闭，避免 Electron/uvicorn 控制台被增量同步细节刷屏；排查问题时在 .env 中改成 true。
INDEXING_DEBUG_LOG = _indexing_settings.debug_log

MAX_TOP_K = 20
