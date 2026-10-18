"""工作台 router 层共享辅助（薄壳）。

router 仅负责依赖注入 + 路由构造；公共业务辅助统一从 service 层复用，避免逻辑散落在
router。保留本模块以兼容既有子路由的 import 路径（`from app.routers.workbench._common
import ...`），现仅转出子路由实际使用的名字：
`dep`、`get_current_user`、`get_db`、`require_teacher`、`new_router`。
"""
from fastapi import APIRouter

from app.database import get_db  # noqa: F401  (re-export)
from app.deps import get_current_user, require_teacher  # noqa: F401  (re-export)

# 教师权限依赖别名（供子路由 `Depends(dep)` 使用）
dep = require_teacher


def new_router(tag: str) -> APIRouter:
    """创建带统一前缀与标签的子路由。"""
    return APIRouter(prefix="/api", tags=[tag])
