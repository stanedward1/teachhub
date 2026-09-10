"""教师工作台子路由共享依赖。

拆分自原 workbench.py，供各资源域子模块复用公共 import 与权限辅助。
"""
from fastapi import APIRouter, Depends, HTTPException

from app.database import get_db
from app.deps import require_teacher, get_current_user
from app.audit import (
    attach_student,
    serialize_list_with_students,
    audit,
    student_name,
    active_student_id_query,
    active_classroom_id_query,
    batch_student_map,
)
from app.permissions import (
    is_any_admin,
    get_teacher_class_ids,
    is_student_in_teacher_classes,
    is_teacher_class_owner,
    apply_student_class_filter,
    apply_teacher_student_filter,
    ensure_student_operable,
    ensure_class_operable,
)
from app.utils import to_dict, normalize_page, parse_date

# 每个子模块创建一个独立的 APIRouter，统一挂在 /api 前缀下
dep = require_teacher


def new_router(tag: str) -> APIRouter:
    """创建带统一前缀与标签的子路由。"""
    return APIRouter(prefix="/api", tags=[tag])
