from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from graph_routes import router as graph_router
from rag_routes import router as rag_router

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


app.include_router(graph_router)
app.include_router(rag_router)


@app.get("/")
async def root():
    """根路由健康提示；不访问数据库，不影响状态。"""
    # 轻量根路由，便于手动确认服务已启动。
    return {"message": "OC Creative Assistant backend is running"}


@app.get("/health")
async def health():
    """进程可用性检查；返回固定结构供 Electron/脚本轮询。"""
    # Electron 主进程和开发脚本会轮询该接口判断后端是否可用。
    return {"status": "ok", "service": "backend"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    """本地连通性示例接口；name 来自路径参数，不访问业务数据。"""
    # 示例接口保留给本地连通性测试，不参与当前 graph 业务。
    return {"message": f"Hello {name}"}
