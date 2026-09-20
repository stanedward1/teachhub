"""班级日志路由层（B1 分层）。

仅保留：路由声明、依赖注入、参数解析、调用 ``classlog_service``、返回。
业务逻辑与数据访问见 ``app/services/classlog_service.py``。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_teacher, get_current_user
from app.models import ClassPlan, TeacherPlan, User
from app.schemas import (
    PerformanceOut,
    ReturnRecordCreate,
    ReturnRecordOut,
    StudentCommentOut,
    TalkCreate,
    TalkOut,
    WorkLogCreate,
)
from app.services import classlog_service

router = APIRouter(prefix="/api", tags=["班级日志"])

dep = require_teacher


# ---------------- 工作日志 ----------------
@router.get("/work-logs")
def list_work_logs(page: int = 1, page_size: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.list_work_logs(db, page, page_size, user)


@router.post("/work-logs")
def create_work_log(payload: WorkLogCreate, user=Depends(dep), db: Session = Depends(get_db)):
    return classlog_service.create_work_log(db, user, payload)


@router.put("/work-logs/{log_id}")
def update_work_log(log_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.update_work_log(db, log_id, payload, user)


@router.delete("/work-logs/{log_id}")
def delete_work_log(log_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.delete_work_log(db, log_id, user)


# ---------------- 班级计划 / 教师计划 ----------------
def _plan_routes(model, prefix):
    @router.get(f"/{prefix}")
    def list_plans(page: int = 1, page_size: int = 20, plan_type: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        return classlog_service.list_plans(db, model, page, page_size, plan_type, user)

    @router.post(f"/{prefix}")
    def create_plan(payload: dict, user=Depends(dep), db: Session = Depends(get_db)):
        return classlog_service.create_plan(db, model, user, payload)

    @router.put(f"/{prefix}/{{item_id}}")
    def update_plan(item_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        return classlog_service.update_plan(db, model, item_id, payload, user)

    @router.delete(f"/{prefix}/{{item_id}}")
    def delete_plan(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        return classlog_service.delete_plan(db, model, item_id, user)


_plan_routes(ClassPlan, "class-plans")
_plan_routes(TeacherPlan, "teacher-plans")


# ---------------- 课程表 ----------------
@router.get("/schedules")
def list_schedules(class_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.list_schedules(db, class_id, user)


@router.post("/schedules")
def create_schedule(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.create_schedule(db, payload, user)


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.delete_schedule(db, schedule_id, user)


# ---------------- 班级活动 ----------------
@router.get("/activities")
def list_activities(page: int = 1, page_size: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.list_activities(db, page, page_size, user)


@router.post("/activities")
def create_activity(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.create_activity(db, payload, user)


@router.delete("/activities/{activity_id}")
def delete_activity(activity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.delete_activity(db, activity_id, user)


# ---------------- 师生谈心 ----------------
@router.get("/talks")
def list_talks(page: int = 1, page_size: int = 20, student_id: int | None = None, class_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.list_talks(db, page, page_size, student_id, class_id, user)


@router.post("/talks", response_model=TalkOut, status_code=201)
def create_talk(payload: TalkCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.create_talk(db, payload, user)


@router.delete("/talks/{talk_id}")
def delete_talk(talk_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.delete_talk(db, talk_id, user)


# ---------------- 返校记录 ----------------
@router.get("/return-records")
def list_return_records(page: int = 1, page_size: int = 20, student_id: int | None = None, class_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.list_return_records(db, page, page_size, student_id, class_id, user)


@router.post("/return-records", response_model=ReturnRecordOut, status_code=201)
def create_return_record(payload: ReturnRecordCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.create_return_record(db, payload, user)


@router.delete("/return-records/{record_id}")
def delete_return_record(record_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.delete_return_record(db, record_id, user)


# ---------------- 学生表现 ----------------
@router.get("/performances")
def list_performances(page: int = 1, page_size: int = 20, student_id: int | None = None, class_id: int | None = None, ptype: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.list_performances(db, page, page_size, student_id, class_id, ptype, user)


# 必须声明在 `/performances/{performance_id}` 之前：否则 "summary" 会被当成路径参数匹配掉
@router.get("/performances/summary")
def summarize_performances(student_id: int | None = None, class_id: int | None = None, ptype: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """筛选范围内的积分汇总（净变动 / 加分 / 扣分 / 记录数 / 涉及学生数）。"""
    return classlog_service.summarize_performances(db, student_id, class_id, ptype, user)


@router.post("/performances", response_model=PerformanceOut, status_code=201)
def create_performance(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.create_performance(db, payload, user)


@router.delete("/performances/{performance_id}")
def delete_performance(performance_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.delete_performance(db, performance_id, user)


# ---------------- 学生评语 ----------------
@router.get("/student-comments/suggest")
def suggest_student_comment(student_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """基于学生已有数据（成绩/表现/考勤/积分）生成评语草稿，供教师参考编辑。"""
    return classlog_service.suggest_student_comment(db, student_id, user)


@router.get("/student-comments")
def list_student_comments(page: int = 1, page_size: int = 20, student_id: int | None = None, class_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.list_student_comments(db, page, page_size, student_id, class_id, user)


@router.post("/student-comments", response_model=StudentCommentOut, status_code=201)
def create_student_comment(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.create_student_comment(db, payload, user)


@router.put("/student-comments/{comment_id}", response_model=StudentCommentOut)
def update_student_comment(comment_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.update_student_comment(db, comment_id, payload, user)


@router.delete("/student-comments/{comment_id}")
def delete_student_comment(comment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return classlog_service.delete_student_comment(db, comment_id, user)
