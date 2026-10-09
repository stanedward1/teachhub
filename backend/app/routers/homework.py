"""作业提交平台路由层（B1 分层）。

仅保留：路由声明、依赖注入、参数解析、调用 ``homework_service``、返回。
业务逻辑与数据访问见 ``app/services/homework_service.py``。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import (
    get_current_user,
    require_student,
    require_teacher,
    require_teacher_only,
)
from app.schemas import AiCompanionAsk, SubmissionCommentCreate, SubmissionCreate
from app.services import ai_companion, ai_companion_teacher, homework_service

router = APIRouter(prefix="/api/homework", tags=["作业提交平台"])


# ---------------- 作业任务 ----------------
@router.get("/assignments")
def list_assignments(
    class_id: int | None = None,
    page: int | None = Query(None, ge=1),
    page_size: int | None = Query(None, ge=1),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # page/page_size 均缺省时走 service 层全量兼容路径（返回结构与历史完全一致）
    return homework_service.list_assignments(db, class_id, user, page, page_size)


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
    page: int | None = Query(None, ge=1),
    page_size: int | None = Query(None, ge=1),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # page/page_size 均缺省时走 service 层全量兼容路径（返回结构与历史完全一致）
    return homework_service.list_submissions(db, assignment_id, user, page, page_size)


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


@router.get("/assignments/{assignment_id}/ai-grade/progress")
def ai_grade_progress(
    assignment_id: int,
    user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """查询整份作业的 AI 批改进度（前端轮询用）。

    纯聚合、无写操作、无外呼；返回体的终止字段 `finished` 表示「没有在跑的任务了」。
    """
    return homework_service.ai_grade_progress(db, assignment_id, user)


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
    payload: SubmissionCreate,
    user=Depends(require_student),
    db: Session = Depends(get_db),
):
    return homework_service.submit(db, assignment_id, payload.model_dump(), user)


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


# ---------------- AI 学伴（docs/DESIGN-AI学伴.md §4.2 / §14.2） ----------------
# 分层：本段只做「声明路径 + 依赖注入 + 参数解析 + 调用 service + 返回」；业务逻辑与
# 数据访问见 `services/ai_companion.py`（学生链路）与 `services/ai_companion_teacher.py`
# （教师侧只读）。

# ---- 学生侧 3 个端点（🔴 必须 require_student）----
# 🔴 设计标红的陷阱：项目里 `GET /api/homework/assignments/{id}` 挂的是
# `get_current_user` 而非 `require_student` ⇒ **教师也能调它**（设计 N6）。学伴端点
# **必须显式挂 require_student**，否则会出现「教师或任意登录用户以学生身份提问、
# 消耗学生额度」的口子。
@router.post("/assignments/{assignment_id}/companion/ask")
def companion_ask(
    assignment_id: int,
    payload: AiCompanionAsk,
    user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """学生提问（同步阻塞调用模型，超时见 `settings.AI_COMPANION_TIMEOUT=25`）。

    请求体仅 `{"question": str}`（校验在 service 层，长度 1..1500）；**禁止前端传
    题干 / 历史 / 开关**（设计 D2：不信任前端传来的上下文）。
    越权（非本班作业）⇒ 403；开关关闭 ⇒ 403；额度尽 ⇒ 429；无凭证 ⇒ 503；
    模型失败 ⇒ 502（超时 / 截断差异化文案，由 service 抛 HTTPException）。
    """
    # 🔴 body 走 AiCompanionAsk schema（question: str | None = None，无长度约束）：
    # 字段缺省/空值仍落 service 层 400（口径不变）；非字符串（int/bool）由 Pydantic
    # 422 拦截 —— 裸 dict 时代会在 service 层 .strip()/len() 上 500。
    return ai_companion.ask(db, assignment_id, payload.question, user)


@router.get("/assignments/{assignment_id}/companion/history")
def companion_history(
    assignment_id: int,
    user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """取本学生在**该作业**下的会话历史（无会话则 `conversation_id=null` + 空数组，不 404）。"""
    return ai_companion.history(db, assignment_id, user)


@router.get("/assignments/{assignment_id}/companion/quota")
def companion_quota(
    assignment_id: int,
    user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """取本学生在该作业下**今日的学伴额度读数**（docs/DESIGN-AI学伴配额.md D4）。

    返回 `{enabled, remaining, limit, used, day}`：学生端抽屉打开 / 提问成功后调用，
    显示「今日剩余 N 次」（**重拉权威值，不本地减一**）。

    只读、无副作用（不写库、不扣额）。`day` 已由 service 层 `stringify_dates`（S12）。
    🔴 只挂 `require_student`（绝不能挂 `get_current_user`）：否则教师可读学生配额。
    越权（非本班作业）⇒ 403；作业不存在 ⇒ 404。
    """
    return ai_companion.quota(db, assignment_id, user)


@router.delete("/assignments/{assignment_id}/companion")
def companion_clear(
    assignment_id: int,
    user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """学生清空自己在该作业下的会话（只删本会话，**不影响额度**）。"""
    return ai_companion.clear(db, assignment_id, user)


# ---- 教师侧 2 个端点（🔴 仅教师，管理员不放行）----
# 设计 §14.2.1：本轮**不给管理员开放**（仅教师）。`require_teacher` 会把
# school_admin / super_admin 一并放行，故此处用 `require_teacher_only` 严格限定 role=teacher，
# 满足「超管调教师端点 ⇒ 403」的验收口径。教师侧**只读**（X6），无写端点。
@router.get("/assignments/{assignment_id}/companion/conversations")
def companion_conversations(
    assignment_id: int,
    page: int = 1,
    page_size: int = 20,
    user=Depends(require_teacher_only),
    db: Session = Depends(get_db),
):
    """列出**该作业下**本班学生的学伴会话（一个学生会话 = 一行，**不含消息内容**）。

    权限口径 = 班主任 ∪ 科任（`get_teacher_class_ids` / `apply_teacher_student_filter`），
    作业级入口另放行**该作业创建者**（「创建者保留管理权」，2026-10-09）；
    非本班且非创建者 ⇒ 403。列表审计 action = `companion_view_list`（传 class_id，不传 student_id）。
    """
    return ai_companion_teacher.list_companion_conversations(
        db, assignment_id, user, page, page_size
    )


@router.get("/companion/conversations/{conversation_id}")
def companion_conversation_detail(
    conversation_id: int,
    user=Depends(require_teacher_only),
    db: Session = Depends(get_db),
):
    """取单个会话的完整消息（含学生提问原文 + AI 全文）。

    🔴 三重硬校验（§14.2，缺一不可）：① 会话存在；② 其作业本班可访问（或系该教师所创建）；③ 该会话
    `student_id` 落在教师可见班级范围内。任不满足 ⇒ **404**（不泄露会话存在性）。
    详情审计 action = `companion_view_detail`（传 student_id）。
    """
    return ai_companion_teacher.get_companion_conversation(db, conversation_id, user)
