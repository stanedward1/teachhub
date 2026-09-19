"""教师工作台 service 层共享依赖与辅助。

自 `app/routers/workbench/_common.py` 迁移而来：仅承载业务无关的公共 import 与权限
辅助，供各 `<domain>_service.py` 复用；**不含** APIRouter / 路由构造（保留在 router 层）。
"""
from datetime import date, datetime

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
)
from app.utils import normalize_page, parse_date, to_dict

# 教师权限依赖别名（供 router 层 `Depends(dep)` 使用）
dep = require_teacher


def stringify_dates(d: dict) -> dict:
    """把 dict 中的 ``date`` / ``datetime`` 值转为 ISO 字符串（原地修改并返回）。

    供**带 `response_model` 的写接口**使用：响应模型中 `start_date` / `created_at` 等字段
    声明为 ``str``，而 Pydantic v2 不会把 date/datetime 强转为 str（否则触发
    ``ResponseValidationError``）。这里统一转为与 FastAPI ``jsonable_encoder`` 一致的
    ISO 形态，保证响应 JSON 与其它未声明 response_model 的列表接口形态一致。
    """
    if not isinstance(d, dict):
        return d
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, date):
            d[k] = v.isoformat()
    return d


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
    "require_teacher",
    "serialize_list_with_students",
    "student_name",
    "stringify_dates",
    "to_dict",
    "apply_student_class_filter",
    "apply_teacher_student_filter",
]
