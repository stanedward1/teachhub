"""座位表布局：查询、保存。"""
import json

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.models import Seat
from app.schemas import SeatSave
from app.routers.workbench._common import (
    get_db,
    get_current_user,
    new_router,
    audit,
    ensure_class_operable,
    is_any_admin,
    is_teacher_class_owner,
)

router = new_router("座位表")


@router.get("/seats")
def get_seat(class_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if not is_any_admin(user):
        if not is_teacher_class_owner(db, user.id, class_id):
            raise HTTPException(status_code=403, detail="无权查看该班级座位表")
    s = db.query(Seat).filter(Seat.class_id == class_id).first()
    if not s:
        return {"layout": [], "columns": 6}
    layout = []
    if s.layout:
        try:
            layout = json.loads(s.layout)
        except (json.JSONDecodeError, TypeError):
            layout = []
    return {"layout": layout, "columns": s.columns}


@router.put("/seats")
def save_seat(payload: SeatSave, user=Depends(get_current_user), db: Session = Depends(get_db)):
    class_id = payload.class_id
    ensure_class_operable(db, class_id)
    if not is_any_admin(user):
        if not is_teacher_class_owner(db, user.id, class_id):
            raise HTTPException(status_code=403, detail="无权修改该班级座位表")
    s = db.query(Seat).filter(Seat.class_id == class_id).first()
    if not s:
        s = Seat(class_id=class_id)
        db.add(s)
    s.layout = json.dumps(payload.layout, ensure_ascii=False)
    s.columns = payload.columns
    audit(db, user, "save_seat", target=f"保存座位表")
    db.commit()
    return {"ok": True}
