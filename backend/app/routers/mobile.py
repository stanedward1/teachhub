"""移动端专用轻量接口（路由层：仅声明路径 / 依赖注入 / 参数解析 / 调用 service / 返回）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.services import mobile_service

router = APIRouter(prefix="/api", tags=["移动端"])


@router.get("/mobile/students")
def mobile_students(
    class_id: int | None = None,
    keyword: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """移动端学生速查列表（精简字段，默认仅返回在籍学生）。"""
    return mobile_service.mobile_students(db, user, class_id, keyword)


@router.get("/mobile/students/{student_id}/overview")
def mobile_student_overview(
    student_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """移动端学生画像概览：五维雷达 + 成绩/积分/表现等关键摘要。"""
    return mobile_service.mobile_student_overview(db, user, student_id)
