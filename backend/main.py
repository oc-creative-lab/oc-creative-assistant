"""兼容旧 `main:app` 导入路径的薄入口。"""

from app.main import app

__all__ = ["app"]
