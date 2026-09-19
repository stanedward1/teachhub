"""学生考勤点名接口（路由层：仅声明路径 / 依赖注入 / 参数解析 / 调用 service / 返回）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import AttendanceCheckin
from app.services import attendance_service

router = APIRouter(prefix="/api", tags=["考勤"])


@router.get("/attendance")
def list_attendance(
    class_id: int = Query(..., gt=0, description="班级 ID"),
    date: str = Query(..., min_length=1, description="考勤日期（YYYY-MM-DD）"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询某班级某日的考勤：返回该班在籍学生及其状态（未点名默认出勤）。"""
    return attendance_service.list_attendance(db, user, class_id, date)


@router.post("/attendance/checkin", status_code=201)
def checkin(payload: AttendanceCheckin, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """批量提交点名结果（存在则更新，不存在则新增）。"""
    return attendance_service.checkin(db, user, payload)


@router.get("/attendance/summary")
def attendance_summary(
    class_id: int = Query(..., gt=0, description="班级 ID"),
    start_date: str = Query(..., min_length=1, description="开始日期（YYYY-MM-DD）"),
    end_date: str = Query(..., min_length=1, description="结束日期（YYYY-MM-DD）"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """出勤率统计：某班级某日期范围内的出勤率、状态分布与逐日趋势。"""
    return attendance_service.attendance_summary(db, user, class_id, start_date, end_date)
