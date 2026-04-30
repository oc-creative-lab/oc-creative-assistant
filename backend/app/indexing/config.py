"""向量索引配置常量。

本模块集中管理 ChromaDB collection 名称、embedding 维度和检索相关默认值。
路径配置来自 `app.core.paths`，确保源码迁入 `app/` 后仍写入 `backend/data`。
"""

from app.core.paths import CHROMA_PATH


CHROMA_COLLECTION_NAME = "oc_lore_nodes"
DEFAULT_RELATION_LABEL = "关联"
DEFAULT_RELATION_TYPE = "relates_to"
DEFAULT_NODE_STATUS = "draft"
EMBEDDING_DIMENSION = 64
MAX_TOP_K = 20
