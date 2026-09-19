"""学生数字画像：综合画像 + 标签管理（薄路由，逻辑见 app/services/workbench/profile_service.py）。"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.routers.workbench._common import get_current_user, get_db, new_router
from app.schemas import StudentTagCreate
from app.services.workbench import profile_service

router = new_router("学生画像")


@router.get("/students/{student_id}/profile")
def get_student_profile(student_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return profile_service.get_student_profile(db, user, student_id)


@router.post("/students/{student_id}/tags")
def add_student_tag(student_id: int, payload: StudentTagCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return profile_service.add_student_tag(db, user, student_id, payload)


@router.delete("/students/{student_id}/tags/{tag_id}")
def remove_student_tag(student_id: int, tag_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return profile_service.remove_student_tag(db, user, student_id, tag_id)
