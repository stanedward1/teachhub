"""请假/考勤记录：查询、增删改（薄路由，逻辑见 app/services/workbench/leaves_service.py）。"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.routers.workbench._common import get_current_user, get_db, new_router
from app.schemas import LeaveCreate, LeaveOut, LeaveUpdate
from app.services.workbench import leaves_service

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
    return leaves_service.list_leaves(
        db, user, page=page, page_size=page_size, student_id=student_id, class_id=class_id, status=status
    )


@router.post("/leaves", response_model=LeaveOut)
def create_leave(payload: LeaveCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return leaves_service.create_leave(db, user, payload)


@router.put("/leaves/{leave_id}", response_model=LeaveOut)
def update_leave(leave_id: int, payload: LeaveUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return leaves_service.update_leave(db, user, leave_id, payload)


@router.delete("/leaves/{leave_id}")
def delete_leave(leave_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return leaves_service.delete_leave(db, user, leave_id)
