"""教师工作台路由包：按资源域拆分，聚合导出统一的 `router`。

原单文件 workbench.py（1374 行）拆分为 scores / leaves / communications /
resources / exams / seats / imports / profile / reports 九个子模块，各自持有
独立的 APIRouter，这里用主 router 聚合，供 main.py 一次性 include。

对外契约不变：`from app.routers import workbench` 后 `workbench.router` 仍可用。
"""
from fastapi import APIRouter

from app.routers.workbench import (
    scores,
    leaves,
    communications,
    resources,
    exams,
    seats,
    imports,
    profile,
    reports,
)

# 主路由：汇总所有子模块的路由，保持与拆分前完全一致的接口路径与行为
router = APIRouter()
for sub in (scores, leaves, communications, resources, exams, seats, imports, profile, reports):
    router.include_router(sub.router)

__all__ = ["router"]
