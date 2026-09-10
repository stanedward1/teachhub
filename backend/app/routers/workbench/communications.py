"""家校沟通记录：查询、增删。"""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.models import Communication
from app.schemas import CommunicationCreate, CommunicationOut
from app.routers.workbench._common import (
    get_db,
    get_current_user,
    new_router,
    audit,
    student_name,
    active_student_id_query,
    apply_student_class_filter,
    apply_teacher_student_filter,
    ensure_student_operable,
    is_any_admin,
    is_student_in_teacher_classes,
    attach_student,
    serialize_list_with_students,
    to_dict,
    normalize_page,
)

router = new_router("家校沟通")


@router.get("/communications")
def list_communications(page: int = 1, page_size: int = 20, student_id: int | None = None, class_id: int | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    page, page_size = normalize_page(page, page_size)
    q = db.query(Communication)
    q = q.filter(Communication.student_id.in_(active_student_id_query(db)))
    q, denied = apply_teacher_student_filter(db, user, q, Communication)
    if denied:
        return {"items": [], "total": 0}
    if class_id:
        q, denied = apply_student_class_filter(db, user, q, class_id, Communication)
        if denied:
            return {"items": [], "total": 0}
    if student_id:
        if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
            return {"items": [], "total": 0}
        q = q.filter(Communication.student_id == student_id)
    total = q.count()
    rows = q.order_by(Communication.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": serialize_list_with_students(db, rows), "total": total}


@router.post("/communications", response_model=CommunicationOut, status_code=201)
def create_communication(payload: CommunicationCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
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
    return attach_student(db, to_dict(x), x.student_id)


@router.delete("/communications/{communication_id}")
def delete_communication(communication_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
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
