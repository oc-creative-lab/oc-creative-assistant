"""Vector index configuration constants.

This module centrally manages ChromaDB collection names, embedding dimensions, and
retrieval-related default values.
The path configuration comes from `app.core.paths`: in development it defaults to
`backend/data`, and in packaged mode it follows the directory specified by
Electron.
Runtime configuration related to embedding and index debugging is read uniformly
from `app.core.settings`, to avoid .env parsing being scattered across multiple
modules.
"""

from app.core.paths import CHROMA_PATH
from app.core.settings import get_embedding_settings, get_indexing_settings


COLLECTION_BY_NODE_TYPE: dict[str, str] = {
    "character": "oc_characters",
    "worldbuilding": "oc_worldbuilding",
    "plot": "oc_plot",
}
DEFAULT_COLLECTION_NAME = "oc_misc"
DEFAULT_RELATION_LABEL = "related"
DEFAULT_RELATION_TYPE = "relates_to"
DEFAULT_NODE_STATUS = "draft"

# Embedding/index configuration is snapshotted once at module import time, to avoid repeatedly reading .env on the hot path.
_embedding_settings = get_embedding_settings()
_indexing_settings = get_indexing_settings()

# These constants are used by both vector_store and sync; module-level aliases are kept to remain compatible with existing import paths.
EMBEDDING_BASE_URL = _embedding_settings.base_url or ""
EMBEDDING_API_KEY = _embedding_settings.api_key or ""
EMBEDDING_MODEL = _embedding_settings.model
EMBEDDING_DIMENSION = _embedding_settings.dimension

# Index sync logging is off by default, to avoid flooding the Electron/uvicorn console with incremental sync details; set it to true in .env when troubleshooting.
INDEXING_DEBUG_LOG = _indexing_settings.debug_log

MAX_TOP_K = 20
