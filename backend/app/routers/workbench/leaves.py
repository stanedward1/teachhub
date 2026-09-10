"""请假/考勤记录：查询、增删改。"""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.models import Leave
from app.schemas import LeaveCreate, LeaveOut, LeaveUpdate
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
    parse_date,
)

router = new_router("请假/考勤")


@router.get("/leaves")
def list_leaves(
    page: int = 1,
    page_size: int = 20,
    student_id: int | None = None,
    class_id: int | None = None,
    status: str = "",
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, page_size = normalize_page(page, page_size)
    q = db.query(Leave)
    q = q.filter(Leave.student_id.in_(active_student_id_query(db)))
    q, denied = apply_teacher_student_filter(db, user, q, Leave)
    if denied:
        return {"items": [], "total": 0}
    if class_id:
        q, denied = apply_student_class_filter(db, user, q, class_id, Leave)
        if denied:
            return {"items": [], "total": 0}
    if student_id:
        if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
            return {"items": [], "total": 0}
        q = q.filter(Leave.student_id == student_id)
    if status:
        q = q.filter(Leave.status == status)
    total = q.count()
    rows = q.order_by(Leave.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": serialize_list_with_students(db, rows), "total": total}


@router.post("/leaves", response_model=LeaveOut, status_code=201)
def create_leave(payload: LeaveCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
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
    return attach_student(db, to_dict(x), x.student_id)


@router.put("/leaves/{leave_id}", response_model=LeaveOut)
def update_leave(leave_id: int, payload: LeaveUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
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
    return attach_student(db, to_dict(x), x.student_id)


@router.delete("/leaves/{leave_id}")
def delete_leave(leave_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
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
