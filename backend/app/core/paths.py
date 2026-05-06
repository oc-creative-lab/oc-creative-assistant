"""后端运行时路径约定。

源码迁入 `app/` 包后，开发态数据仍默认保留在 `backend/data`。
打包态由 Electron 主进程通过环境变量传入持久化目录，避免 portable 临时解包目录吞掉数据。
本模块集中提供路径常量，避免数据库和向量索引各自依赖 `__file__` 层级推导。
"""

import os
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
"""后端项目根目录；开发态即包含 `app/` 与 `data/` 的 `backend` 目录。"""

DATA_DIR_ENV = "OC_CREATIVE_DATA_DIR"
"""Electron 打包态传给后端的数据目录环境变量名。"""


def _resolve_data_dir() -> Path:
    """解析后端运行时数据目录。

    Electron 打包态显式传入目录，portable 写到 exe 旁边，安装版写到用户数据目录。
    开发态不传环境变量时，继续回退到源码内的 `backend/data`。
    """
    configured_data_dir = os.environ.get(DATA_DIR_ENV)

    if configured_data_dir:
        return Path(configured_data_dir).expanduser().resolve()

    return BACKEND_ROOT / "data"


DATA_DIR = _resolve_data_dir()
"""后端运行时数据目录，SQLite 与 ChromaDB 都写入该目录。"""

DATABASE_PATH = DATA_DIR / "oc_creative.sqlite3"
"""本地 SQLite 数据库文件路径。"""

CHROMA_PATH = DATA_DIR / "chroma"
"""本地 ChromaDB 持久化目录。"""
