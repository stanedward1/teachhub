"""工作台 router 层共享辅助（薄壳）。

router 仅负责依赖注入 + 路由构造；公共业务辅助统一从 service 层复用，避免逻辑散落在
router。保留本模块以兼容既有子路由的 import 路径（`from app.routers.workbench._common
import ...`）。
"""
from fastapi import APIRouter

from app.services.workbench._common import (  # noqa: F401  (re-export)
    active_classroom_id_query,
    active_student_id_query,
    apply_student_class_filter,
    apply_teacher_student_filter,
    attach_student,
    audit,
    batch_student_map,
    dep,
    ensure_class_operable,
    ensure_student_operable,
    get_current_user,
    get_db,
    get_teacher_class_ids,
    is_any_admin,
    is_student_in_teacher_classes,
    is_teacher_class_owner,
    normalize_page,
    parse_date,
    require_teacher,
    serialize_list_with_students,
    student_name,
    to_dict,
)


def new_router(tag: str) -> APIRouter:
    """创建带统一前缀与标签的子路由。"""
    return APIRouter(prefix="/api", tags=[tag])
