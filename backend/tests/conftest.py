"""pytest 全局夹具。

在导入任何 app 模块之前把数据目录指向临时目录，保证测试用全新的 SQLite，
不污染开发库（app.core.paths 在导入时一次性解析路径，必须先设置环境变量）。
"""

import os
import tempfile

import pytest

# 必须在 import app.* 之前设置，否则 paths/database 已用默认路径建好 engine。
_TMP_DATA_DIR = tempfile.mkdtemp(prefix="oc-test-data-")
os.environ["OC_CREATIVE_DATA_DIR"] = _TMP_DATA_DIR


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    """建表一次。TestClient 不用 with 包裹时不会触发 startup 事件，这里兜底。"""
    from app.db.database import init_db

    init_db()
