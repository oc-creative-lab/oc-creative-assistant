"""RAG 配置常量。

集中管理本地向量库路径、collection 名称、默认关系值和检索参数，
避免这些基础配置散落在服务、检索和向量库模块中。
"""

from pathlib import Path


# 保持与原 rag_service.py 完全一致的数据目录：backend/data/chroma。
CHROMA_PATH = Path(__file__).resolve().parent.parent / "data" / "chroma"
CHROMA_COLLECTION_NAME = "oc_lore_nodes"

DEFAULT_RELATION_LABEL = "关联"
DEFAULT_RELATION_TYPE = "relates_to"
DEFAULT_NODE_STATUS = "draft"

EMBEDDING_DIMENSION = 64
MAX_TOP_K = 20
