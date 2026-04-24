from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from graph_routes import router as graph_router

app = FastAPI(title="OC Creative Assistant Backend")

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


@app.get("/")
async def root():
    return {"message": "OC Creative Assistant backend is running"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "backend"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
