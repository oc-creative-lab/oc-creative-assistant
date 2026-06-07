"""RAG service-layer entry point.

The current RAG core logic lives in `app.rag.service`. This service-layer module
is kept so the API layer only depends on `app.services`, and so more agents can be
orchestrated here uniformly as they are integrated later.
"""

from app.rag.service import build_rag_context, search_project_memory

__all__ = ["build_rag_context", "search_project_memory"]
