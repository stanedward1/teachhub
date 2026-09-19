"""座位表布局：查询、保存（薄路由，逻辑见 app/services/workbench/seats_service.py）。"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.routers.workbench._common import get_current_user, get_db, new_router
from app.schemas import SeatSave
from app.services.workbench import seats_service

router = new_router("座位表")


@router.get("/seats")
def get_seat(class_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return seats_service.get_seat(db, user, class_id)


@router.put("/seats")
def save_seat(payload: SeatSave, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return seats_service.save_seat(db, user, payload)
