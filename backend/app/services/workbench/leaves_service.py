"""请假/考勤业务逻辑：查询、增删改。"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Leave
from app.pagination import paginate
from app.schemas import LeaveCreate, LeaveUpdate
from app.services.workbench._common import (
    active_student_id_query,
    apply_student_class_filter,
    apply_teacher_student_filter,
    attach_student,
    audit,
    ensure_student_operable,
    is_any_admin,
    is_student_in_teacher_classes,
    normalize_page,
    parse_date,
    serialize_list_with_students,
    stringify_dates,
    student_name,
    to_dict,
)


def list_leaves(
    db: Session,
    user,
    page: int = 1,
    page_size: int = 20,
    student_id: int | None = None,
    class_id: int | None = None,
    status: str = "",
) -> dict:
    """请假列表（分页）。单次 SQL 取回当前页 + 总数。"""
    page, page_size = normalize_page(page, page_size)
    stmt = select(Leave)
    stmt = stmt.where(Leave.student_id.in_(active_student_id_query(db)))
    stmt, denied = apply_teacher_student_filter(db, user, stmt, Leave)
    if denied:
        return {"items": [], "total": 0}
    if class_id:
        stmt, denied = apply_student_class_filter(db, user, stmt, class_id, Leave)
        if denied:
            return {"items": [], "total": 0}
    if student_id:
        if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
            return {"items": [], "total": 0}
        stmt = stmt.where(Leave.student_id == student_id)
    if status:
        stmt = stmt.where(Leave.status == status)
    rows, total = paginate(db, stmt.order_by(Leave.id.desc()), page, page_size)
    return {"items": serialize_list_with_students(db, rows), "total": total}


def create_leave(db: Session, user, payload: LeaveCreate) -> dict:
    """新增请假记录。"""
    ensure_student_operable(db, payload.student_id)
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, payload.student_id):
        raise HTTPException(status_code=403, detail="无权为该学生创建请假")
    x = Leave(
        student_id=payload.student_id,
        reason=payload.reason,
        start_date=parse_date(payload.start_date),
        end_date=parse_date(payload.end_date),
        status=payload.status,
        image=payload.image,
    )
    db.add(x)
    audit(db, user, "create_leave", target=f"新增请假-{student_name(db, x.student_id)}", student_id=x.student_id, detail=f"事由：{x.reason or '未填写'}；时间：{x.start_date or ''} ~ {x.end_date or ''}")
    db.commit()
    db.refresh(x)
    return stringify_dates(attach_student(db, to_dict(x), x.student_id))


def update_leave(db: Session, user, leave_id: int, payload: LeaveUpdate) -> dict:
    """更新请假记录。"""
    x = db.get(Leave, leave_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    ensure_student_operable(db, x.student_id)
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, x.student_id):
        raise HTTPException(status_code=403, detail="无权修改该请假")
    data = payload.model_dump(exclude_unset=True)
    for f in ("reason", "start_date", "end_date", "status", "image"):
        if f in data and data[f] is not None:
            setattr(x, f, parse_date(data[f]) if f in ("start_date", "end_date") else data[f])
    audit(db, user, "update_leave", target=f"请假#{leave_id}-{student_name(db, x.student_id)}", student_id=x.student_id, detail=f"事由：{x.reason or '未填写'}；时间：{x.start_date or ''} ~ {x.end_date or ''}")
    db.commit()
    db.refresh(x)
    return stringify_dates(attach_student(db, to_dict(x), x.student_id))


def delete_leave(db: Session, user, leave_id: int) -> dict:
    """删除请假记录。"""
    x = db.get(Leave, leave_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    ensure_student_operable(db, x.student_id)
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, x.student_id):
        raise HTTPException(status_code=403, detail="无权删除该请假")
    db.delete(x)
    audit(db, user, "delete_leave", target=f"请假#{leave_id}-{student_name(db, x.student_id)}", student_id=x.student_id, detail=f"事由：{x.reason or '未填写'}")
    db.commit()
    return {"ok": True}
