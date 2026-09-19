"""座位表布局业务逻辑：查询、保存。"""
import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Seat
from app.schemas import SeatSave
from app.services.workbench._common import (
    audit,
    ensure_class_operable,
    is_any_admin,
    is_teacher_class_owner,
)


def get_seat(db: Session, user, class_id: int) -> dict:
    """读取班级座位表（无记录时返回默认布局）。"""
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


def save_seat(db: Session, user, payload: SeatSave) -> dict:
    """保存班级座位表（不存在则新建）。"""
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
