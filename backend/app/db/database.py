"""SQLAlchemy 数据库连接与初始化。

本模块只负责 SQLite engine、Session 工厂、ORM metadata 初始化和旧库轻量兼容。
业务校验放在服务层，向量索引放在 `app.indexing`。
"""

import json
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.paths import DATABASE_PATH


DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"


class Base(DeclarativeBase):
    """所有 ORM 模型共用的 declarative base。"""


# 本地 SQLite 文件放在 backend/data 下；路径集中在 app.core.paths，避免受包层级影响。
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _deserialize_json(value: str | None) -> Any:
    """反序列化 SQLite JSON 字段，并兼容旧库中的纯字符串 meta。

    Args:
        value: SQLAlchemy JSON 反序列化前的原始文本。

    Returns:
        解析后的 Python 对象；旧的非 JSON 字符串会原样返回。
    """
    if value is None:
        return {}

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    json_deserializer=_deserialize_json,
    future=True,
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    """为每个 SQLite 连接启用外键约束。

    SQLite 默认不强制外键；这里保证 `ondelete=\"CASCADE\"` 在桌面本地库中真实生效。
    """
    if isinstance(dbapi_connection, SQLiteConnection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """初始化 ORM 表结构，并为旧 PoC 数据库补齐轻量兼容字段。"""
    # 延迟导入模型，确保 Base.metadata 已注册所有表后再 create_all。
    from app.db.models import EdgeORM, NodeORM, ProjectORM  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema_compatibility()


def _ensure_sqlite_schema_compatibility() -> None:
    """为旧 PoC 数据库补齐新增列。

    当前项目尚未引入完整迁移系统；这里只处理已上线本地库需要的最小兼容。
    """
    with engine.begin() as connection:
        edge_columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(edges)").fetchall()
        }

        if "relation_type" not in edge_columns:
            connection.exec_driver_sql(
                "ALTER TABLE edges ADD COLUMN relation_type VARCHAR NOT NULL DEFAULT 'relates_to'"
            )
