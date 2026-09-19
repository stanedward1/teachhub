"""家校沟通记录业务逻辑：查询、增删。"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Communication
from app.pagination import paginate
from app.schemas import CommunicationCreate, CommunicationOut
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
    serialize_list_with_students,
    stringify_dates,
    student_name,
    to_dict,
)


def list_communications(
    db: Session,
    user,
    page: int = 1,
    page_size: int = 20,
    student_id: int | None = None,
    class_id: int | None = None,
) -> dict:
    """家校沟通列表（分页）。单次 SQL 取回当前页 + 总数。"""
    page, page_size = normalize_page(page, page_size)
    stmt = select(Communication)
    stmt = stmt.where(Communication.student_id.in_(active_student_id_query(db)))
    stmt, denied = apply_teacher_student_filter(db, user, stmt, Communication)
    if denied:
        return {"items": [], "total": 0}
    if class_id:
        stmt, denied = apply_student_class_filter(db, user, stmt, class_id, Communication)
        if denied:
            return {"items": [], "total": 0}
    if student_id:
        if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
            return {"items": [], "total": 0}
        stmt = stmt.where(Communication.student_id == student_id)
    rows, total = paginate(db, stmt.order_by(Communication.id.desc()), page, page_size)
    return {"items": serialize_list_with_students(db, rows), "total": total}


def create_communication(db: Session, user, payload: CommunicationCreate) -> dict:
    """新增沟通记录。"""
    ensure_student_operable(db, payload.student_id)
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, payload.student_id):
        raise HTTPException(status_code=403, detail="无权为该学生创建沟通")
    x = Communication(
        student_id=payload.student_id,
        method=payload.method,
        content=payload.content,
        feedback=payload.feedback,
    )
    db.add(x)
    audit(db, user, "create_communication", target=f"新增沟通-{student_name(db, x.student_id)}", student_id=x.student_id, detail=f"方式：{x.method or ''}；内容：{(x.content or '')[:50]}")
    db.commit()
    db.refresh(x)
    return stringify_dates(attach_student(db, to_dict(x), x.student_id))


def delete_communication(db: Session, user, communication_id: int) -> dict:
    """删除沟通记录。"""
    x = db.get(Communication, communication_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    ensure_student_operable(db, x.student_id)
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, x.student_id):
        raise HTTPException(status_code=403, detail="无权删除该沟通")
    db.delete(x)
    audit(db, user, "delete_communication", target=f"沟通#{communication_id}-{student_name(db, x.student_id)}", student_id=x.student_id)
    db.commit()
    return {"ok": True}
