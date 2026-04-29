from pathlib import Path
import json
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


DATABASE_PATH = Path(__file__).resolve().parent / "data" / "oc_creative.sqlite3"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"


# 所有 ORM 模型共用的 declarative base。
class Base(DeclarativeBase):
    pass


# 本地 SQLite 文件放在 backend/data 下，启动时自动创建目录。
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _deserialize_json(value: str | None) -> Any:
    """兼容旧 SQLite 中的纯字符串 meta；新数据仍按 JSON 正常读取。"""
    if value is None:
        return {}

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


# SQLite 本地桌面 PoC 中足够轻量；check_same_thread=False 让 FastAPI 请求线程可复用连接池。
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    json_deserializer=_deserialize_json,
    future=True,
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """SQLite 默认不强制外键，这里在每个连接上显式开启。"""
    if isinstance(dbapi_connection, SQLiteConnection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """用 ORM metadata 建表；PoC 阶段不引入复杂迁移系统。"""
    # 延迟导入模型，确保 Base.metadata 已注册所有表后再 create_all。
    from models import EdgeORM, NodeORM, ProjectORM  # noqa: F401

    Base.metadata.create_all(bind=engine)
