"""系统级 HTTP 路由。

这些接口不访问业务数据，主要用于本地连通性确认和 Electron/开发脚本健康检查。
"""

import uuid

from fastapi import APIRouter


router = APIRouter(tags=["system"])


_BOOT_ID = uuid.uuid4().hex


@router.get("/")
async def root() -> dict[str, str]:
    """返回后端根路由健康提示。"""
    return {"message": "OC Creative Assistant backend is running"}


@router.get("/health")
async def health() -> dict[str, str]:
    """返回固定健康检查结构, 附带 boot_id 让前端识别后端是否被重启过。"""
    return {"status": "ok", "service": "backend", "boot_id": _BOOT_ID}


@router.get("/hello/{name}")
async def say_hello(name: str) -> dict[str, str]:
    """返回本地连通性示例响应。"""
    return {"message": f"Hello {name}"}