"""作业提交平台路由层（B1 分层）。

仅保留：路由声明、依赖注入、参数解析、调用 ``homework_service``、返回。
业务逻辑与数据访问见 ``app/services/homework_service.py``。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_student, require_teacher
from app.schemas import SubmissionCommentCreate
from app.services import homework_service

router = APIRouter(prefix="/api/homework", tags=["作业提交平台"])


# ---------------- 作业任务 ----------------
@router.get("/assignments")
def list_assignments(
    class_id: int | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return homework_service.list_assignments(db, class_id, user)


@router.get("/assignments/{assignment_id}")
def get_assignment(
    assignment_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return homework_service.get_assignment(db, assignment_id, user)


@router.post("/assignments")
def create_assignment(payload: dict, user=Depends(require_teacher), db: Session = Depends(get_db)):
    return homework_service.create_assignment(db, payload, user)


@router.put("/assignments/{assignment_id}")
def update_assignment(
    assignment_id: int, payload: dict, user=Depends(require_teacher), db: Session = Depends(get_db)
):
    return homework_service.update_assignment(db, assignment_id, payload, user)


@router.delete("/assignments/{assignment_id}")
def delete_assignment(
    assignment_id: int, user=Depends(require_teacher), db: Session = Depends(get_db)
):
    return homework_service.delete_assignment(db, assignment_id, user)


# ---------------- 作业提交 ----------------
@router.get("/assignments/{assignment_id}/submissions")
def list_submissions(
    assignment_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return homework_service.list_submissions(db, assignment_id, user)


@router.get("/assignments/{assignment_id}/unsubmitted")
def unsubmitted_students(
    assignment_id: int,
    user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """未交名单：该作业下发班级中尚未提交的学生（教师/管理员可用）。"""
    return homework_service.unsubmitted_students(db, assignment_id, user)


@router.post("/assignments/{assignment_id}/ai-grade")
def ai_grade_assignment(
    assignment_id: int,
    user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师手动触发 AI 批改：批改该作业下所有**尚未成功批改**的提交。

    非阻塞：仅投递后台线程池后立即返回；总开关关闭 / 无凭证 / 额度耗尽时 400。
    """
    return homework_service.ai_grade_assignment(db, assignment_id, user)


@router.get("/submissions/{submission_id}")
def get_submission(
    submission_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取提交详情（含完整内容 + 教师点评列表）。"""
    return homework_service.get_submission(db, submission_id, user)


@router.post("/submissions/{submission_id}/ai-grade")
def ai_grade_submission(
    submission_id: int,
    user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师手动触发 AI 批改：**单份**提交（已有结果则重跑覆盖）。"""
    return homework_service.ai_grade_submission(db, submission_id, user)


@router.post("/submissions/{submission_id}/comments")
def add_submission_comment(
    submission_id: int,
    payload: SubmissionCommentCreate,
    user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师对提交添加点评（含可选评分）。"""
    # 用请求模型做类型校验（score 非数字 → 422），再转 dict 交服务层，
    # 保持服务层「缺省判空返回 400」的既有语义不变。
    return homework_service.add_submission_comment(db, submission_id, payload.model_dump(), user)


@router.delete("/submissions/{submission_id}/comments/{comment_id}")
def delete_submission_comment(
    submission_id: int,
    comment_id: int,
    user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """删除点评（仅点评者本人或管理员）。"""
    return homework_service.delete_submission_comment(db, submission_id, comment_id, user)


@router.post("/assignments/{assignment_id}/submissions")
def submit(
    assignment_id: int,
    payload: dict,
    user=Depends(require_student),
    db: Session = Depends(get_db),
):
    return homework_service.submit(db, assignment_id, payload, user)


@router.get("/my-submissions")
def my_submissions(user=Depends(require_student), db: Session = Depends(get_db)):
    return homework_service.my_submissions(db, user)


# ---------------- 优秀作品 ----------------
@router.post("/submissions/{submission_id}/excellent")
def mark_excellent(
    submission_id: int,
    payload: dict,
    user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    return homework_service.mark_excellent(db, submission_id, payload, user)


@router.delete("/submissions/{submission_id}/excellent")
def unmark_excellent(
    submission_id: int, user=Depends(require_teacher), db: Session = Depends(get_db)
):
    return homework_service.unmark_excellent(db, submission_id, user)


@router.get("/excellent")
def list_excellent(
    page: int = 1,
    page_size: int = 12,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return homework_service.list_excellent(db, page, page_size, user)


@router.get("/excellent/{excellent_id}")
def get_excellent(
    excellent_id: int,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return homework_service.get_excellent(db, excellent_id, user)


@router.post("/excellent/{excellent_id}/comments")
def add_comment(
    excellent_id: int,
    payload: dict,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return homework_service.add_comment(db, excellent_id, payload, user)
