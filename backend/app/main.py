"""FastAPI 应用入口。

本模块负责创建应用、注册 CORS、中间件、路由和启动初始化。具体业务逻辑位于
`app.services`，数据库连接位于 `app.db`，向量索引位于 `app.indexing`。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.graph import router as graph_router
from app.api.routes.rag import router as rag_router
from app.api.routes.system import router as system_router
from app.db.database import init_db


app = FastAPI(title="OC Creative Assistant Backend")

# Electron 打包时渲染进程可能来自 file://，开发态来自 localhost；只放行这两类本地来源。
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
    """应用启动时初始化 SQLite 表，保证 Electron 拉起后 API 可直接使用。"""
    init_db()


app.include_router(system_router)
app.include_router(graph_router)
app.include_router(rag_router)
