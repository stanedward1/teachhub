"""教师工作台 service 层共享依赖与辅助。

自 `app/routers/workbench/_common.py` 迁移而来：仅承载业务无关的公共 import 与权限
辅助，供各 `<domain>_service.py` 复用；**不含** APIRouter / 路由构造（保留在 router 层）。
"""
from sqlalchemy.orm import Session

from app.audit import (
    active_classroom_id_query,
    active_student_id_query,
    attach_student,
    audit,
    batch_student_map,
    serialize_list_with_students,
    student_name,
)
from app.database import get_db
from app.deps import get_current_user, require_teacher
from app.permissions import (
    apply_student_class_filter,
    apply_teacher_student_filter,
    ensure_class_operable,
    ensure_student_operable,
    get_teacher_class_ids,
    is_any_admin,
    is_student_in_teacher_classes,
    is_teacher_class_owner,
    resolve_school_id_or_400,
)
from app.utils import normalize_page, parse_date, parse_date_or_400, stringify_dates, to_dict

# 教师权限依赖别名（供 router 层 `Depends(dep)` 使用）
dep = require_teacher


def resolve_school_id_for_schools_scope(
    db: Session, user, requested_school_id: int | None
) -> int | None:
    """解析「学校级实体」（资源 / 试卷）的归属 school_id。

    **委托** `app.permissions.resolve_school_id_or_400`（唯一真源），名称与签名保持不变以
    兼容既有调用方；行为逐字不变 —— 详见真源函数的说明。
    """
    return resolve_school_id_or_400(db, user, requested_school_id)


__all__ = [
    "active_classroom_id_query",
    "active_student_id_query",
    "attach_student",
    "audit",
    "batch_student_map",
    "dep",
    "ensure_class_operable",
    "ensure_student_operable",
    "get_current_user",
    "get_db",
    "get_teacher_class_ids",
    "is_any_admin",
    "is_student_in_teacher_classes",
    "is_teacher_class_owner",
    "normalize_page",
    "parse_date",
    "parse_date_or_400",
    "require_teacher",
    "resolve_school_id_for_schools_scope",
    "serialize_list_with_students",
    "student_name",
    "stringify_dates",
    "to_dict",
    "apply_student_class_filter",
    "apply_teacher_student_filter",
]
