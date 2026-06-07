"""FastAPI application entry point.

This module is responsible for creating the app, registering CORS, middleware,
routes, and startup initialization. The actual business logic lives in
`app.services`, the database connection in `app.db`, and the vector index in
`app.indexing`.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.chat import router as chat_router
from app.api.routes.graph import router as graph_router
from app.api.routes.projects import router as projects_router
from app.api.routes.rag import router as rag_router
from app.api.routes.system import router as system_router
from app.db.database import init_db
from app.services.graph_store import ensure_default_project


app = FastAPI(title="OC Creative Assistant Backend")

# When packaged with Electron the renderer process may come from file://, and in
# dev mode from localhost; only allow these two kinds of local origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    """Initialize the SQLite tables on app startup, so the API is ready to use as soon as Electron launches it."""
    init_db()
    ensure_default_project()


app.include_router(system_router)
# graph_router must be registered before projects_router: its literal route
# /api/projects/default would otherwise be matched first by projects_router's
# dynamic route /api/projects/{project_id} and turned into a 404.
app.include_router(graph_router)
app.include_router(projects_router)
app.include_router(rag_router)
app.include_router(chat_router)
