"""后端运行时路径约定。

源码迁入 `app/` 包后，运行时数据仍必须保留在 `backend/data`。
本模块集中提供路径常量，避免数据库和向量索引各自依赖 `__file__` 层级推导。
"""

from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
"""后端项目根目录，即包含 `app/` 与 `data/` 的 `backend` 目录。"""

DATA_DIR = BACKEND_ROOT / "data"
"""后端运行时数据目录，SQLite 与 ChromaDB 都写入该目录。"""

DATABASE_PATH = DATA_DIR / "oc_creative.sqlite3"
"""本地 SQLite 数据库文件路径。"""

CHROMA_PATH = DATA_DIR / "chroma"
"""本地 ChromaDB 持久化目录。"""
