"""作业提交平台业务服务层。

承载「作业任务 / 作业提交 / 点评 / 优秀作品 / 作品评论」的业务逻辑与数据访问。router
仅做路由声明、依赖注入、参数解析与结果返回。

性能约定（B2）：
- 列表分页统一走 ``app.pagination.paginate``（窗口函数单查询），消除原 ``q.count()``
  二次往返。
- 列表序列化中的班级名 / 创建者名 / 提交数 / 是否提交等取值改为一次批量查询，
  消除逐行 ``db.get`` 与逐行 ``count()`` 的 N+1；``attachments`` 关系用 ``selectinload``
  预加载，避免逐行懒加载。

约束：服务函数首参 ``db: Session``，可抛 ``HTTPException``；本模块不 import router。
"""
import logging
import os

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.audit import batch_student_avatar_map, batch_student_map, audit
from app.pagination import paginate
from app.models import (
    AiGradingResult,
    Assignment,
    AssignmentAttachment,
    Classroom,
    ExcellentWork,
    Student,
    Submission,
    SubmissionComment,
    User,
    WorkComment,
)
from app.models.ai import STATUS_PENDING, STATUS_SUCCESS
from app.permissions import (
    is_any_admin,
    ensure_class_operable,
    ensure_student_operable,
    get_student_avatar,
    get_student_by_account,
    get_teacher_class_ids,
    is_teacher_class_owner,
)
from app.utils import normalize_page, to_dict
from app.uploads import ensure_upload_path, resolve_upload_path
from app.services import ai_grading

logger = logging.getLogger("teachhub.homework")


# ---------------- 内部辅助 ----------------
def _check_student_access(assignment: Assignment, user: User):
    if user.role == "student" and assignment.class_id != user.class_id:
        raise HTTPException(status_code=403, detail="无权访问该任务")


def _check_teacher_assignment_access(db: Session, user: User, assignment: Assignment):
    """教师可访问「自己负责班级」的作业/提交，或**自己创建**的作业；管理员不受限。

    🔴 「创建者保留管理权」（2026-10-09 用户拍板）：``assignment.created_by`` 与
    「班主任 ∪ 科任」（``is_teacher_class_owner``）**并列**为放行条件，满足其一即可。
    理由：写路径本来就认创建者（``update_assignment`` / ``delete_assignment`` 里的
    ``a.created_by != user.id and not is_any_admin(user)`` 判断），读路径若不认，会出现
    「能改能删、却打不开」的自相矛盾（同类缺陷模式见 D-403-1）。
    ⚠️ 非越权：``school_id`` 仍由 ORM 事件注入，跨校不可见。
    ⚠️ 副作用：创建者即使已不带该班，也**能触发该作业的 AI 批改**（消耗学校/平台额度）
    —— 与写路径「能改能删」一致，属「创建者保留管理权」口径的必然结果。
    """
    if assignment is None:
        return
    if user.role == "teacher":
        if is_teacher_class_owner(db, user.id, assignment.class_id):
            return
        if assignment.created_by is not None and assignment.created_by == user.id:
            return
        raise HTTPException(status_code=403, detail="无权访问其他班级的任务")


def _ensure_submission_operable(db: Session, submission: Submission):
    """校验提交对应的学生是否可被教师操作（退学/毕业限制）。"""
    ensure_student_operable(db, submission.student_id)


def _attachments_out(a: Assignment) -> list:
    """把作业附件转成对外结构 [{id, filename, filepath}]。"""
    return [
        {"id": att.id, "filename": att.filename, "filepath": att.filepath}
        for att in a.attachments
    ]


def _remove_upload_files(paths) -> None:
    """删除上传目录内的文件（失败静默，不阻断主流程）。

    🔴 路径一律经 `uploads.resolve_upload_path` 归一化并**约束在上传目录内**。
    历史实现直接 `os.path.join(settings.UPLOAD_DIR, p.lstrip("/").replace("/", os.sep))`：
    `lstrip("/")` 只挡前导斜杠、对 `..` 毫无防护，而这里的入参来自
    `submissions.filepath` / `attachments[].filepath`（**请求体可控**）⇒ 学生提交
    `../../x` 再重交换路径，就能删掉上传目录之外的任意文件
    （见 `docs/REVIEW-2026-09-25-code-audit.md` P0-A，已用探针实证）。

    另：用 `os.path.isfile` 而非 `os.path.exists` —— 目录永不进入 `os.remove`。
    """
    for p in paths or []:
        if not p:
            continue
        try:
            full = resolve_upload_path(p)
        except ValueError:
            logger.warning("跳过非法的附件路径，不删除：%r", p)
            continue
        try:
            if os.path.isfile(full):
                os.remove(full)
        except OSError:
            pass


def _sync_attachments(a: Assignment, attachments) -> None:
    """同步作业附件（传入 [{filename, filepath}, ...]，整体替换旧附件），并清理被移除的附件文件。

    🔴 每个 `filepath` 都要先过 `ensure_upload_path`（非法 ⇒ **400**）：附件路径同样来自
    请求体，落库后会成为 `delete_assignment` / `_sync_attachments` 的删除目标
    （与 P0-A 同一条攻击链的另一个入口）。
    """
    items = [
        att
        for att in (attachments or [])
        if isinstance(att, dict) and att.get("filename") and att.get("filepath")
    ]
    for att in items:
        ensure_upload_path(att["filepath"])
    new_paths = {att["filepath"] for att in items}
    removed = [att.filepath for att in a.attachments if att.filepath and att.filepath not in new_paths]
    a.attachments.clear()
    for att in items:
        a.attachments.append(
            AssignmentAttachment(filename=att["filename"], filepath=att["filepath"])
        )
    _remove_upload_files(removed)


def _ai_grading_out(result: AiGradingResult | None, *, for_student: bool = False) -> dict | None:
    """把 AI 批改结果转成对外结构（无结果返回 None）。

    学生端不返回 `error`：失败原因可能含服务商回执等内部信息，
    且 PRD §6 F5 要求「处理中 / 失败不暴露内部状态」。
    """
    if result is None:
        return None
    data = {
        "status": result.status,
        "provider": result.provider,
        "model": result.model,
        "score": result.score,
        "summary": result.summary,
        "strengths": result.strengths,
        "improvements": result.improvements,
        "attachment_used": result.attachment_used,
        "is_excellent_candidate": bool(result.is_excellent_candidate),
        "excellent_reason": result.excellent_reason,
        "updated_at": result.updated_at or result.created_at,
    }
    if not for_student:
        data["error"] = result.error
    return data


def _ai_status_map(db: Session, submission_ids: list[int]) -> dict[int, dict]:
    """批量取 AI 批改状态：``{submission_id: {status, score, is_excellent_candidate}}``。

    一次查询覆盖整页，避免逐行查询造成 N+1；尚无批改结果的提交不出现在 map 中。
    """
    if not submission_ids:
        return {}
    rows = (
        db.query(
            AiGradingResult.submission_id,
            AiGradingResult.status,
            AiGradingResult.score,
            AiGradingResult.is_excellent_candidate,
        )
        # 跳过租户过滤：这里的 submission_ids 已由调用方按租户范围查出，
        # 而结果行按全局唯一的 submission_id 1:1 对应；带过滤会让归属异常的行
        # 显示成「未批改」（列表与详情口径不一致）。
        .execution_options(skip_tenant_filter=True)
        .filter(AiGradingResult.submission_id.in_(submission_ids))
        .all()
    )
    return {
        sid: {
            "status": status,
            "score": score,
            "is_excellent_candidate": bool(is_excellent_candidate),
        }
        for sid, status, score, is_excellent_candidate in rows
    }


def _discard_ai_grading(db: Session, submission_id: int) -> None:
    """作废某次提交的 AI 批改结果（学生重交后调用，失败静默）。

    批改结果是**对某一版提交内容**的评价，重交后不再成立；
    留着会让师生误以为当前内容已被批改过。删除后教师可再次手动触发。
    """
    try:
        # 注意：ORM 的批量 delete/update **不受**租户过滤（`tenant.py` 只对 SELECT 注入），
        # 因此这里是全局按 submission_id 删除 —— 这正是我们要的（含归属异常的历史行）。
        db.query(AiGradingResult).filter(
            AiGradingResult.submission_id == submission_id
        ).delete()
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("作废旧 AI 批改结果失败 submission=%s", submission_id)


# ---------------- AI 批改（教师手动触发，§F3） ----------------
def ai_grade_submission(db: Session, submission_id: int, user: User) -> dict:
    """教师手动批改**单份**提交（允许对已有结果重跑覆盖）。

    - 已有 `pending` 结果行 ⇒ 正在批改中，本次幂等空操作返回（`queued=0`），
      避免教师双击 / 多标签页重复外呼并重复预扣配额（批量入口已修同一类问题）。
    - 已有 `success` 结果行 ⇒ **照常重跑**（设计内能力，由前端二次确认把关）。

    Raises:
        HTTPException: 提交不存在 404；非本班且非创建者教师 403。
    """
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(status_code=404, detail="提交不存在")
    a = db.get(Assignment, s.assignment_id)
    _check_teacher_assignment_access(db, user, a)

    # 幂等守卫：该提交已有 `pending` 结果行 ⇒ 正在批改中，本次为教师双击 / 多标签页
    # 造成的重复投递，直接空操作返回（不重复外呼、不重复预扣配额）。返回 200 而非 400
    # —— 这不是错误，是「已经在做了」。`success` 一律放行：允许按设计对已有结果重跑覆盖，
    # 前端对重批做二次确认（此处绝不做静默跳过，否则会剥夺教师重批能力）。
    row = (
        db.query(AiGradingResult)
        # 🔴 必须跳过租户过滤：`submission_id` 是**全局唯一**键，结果行的身份与租户无关。
        # 结果行 `school_id` 可能为 NULL 或属他校（历史脏数据），当前教师租户读不到 ⇒
        # 守卫失效 → 继续 `request_grading` → 被 `_apply_prewrite` 跳过（claimed=[]）→
        # 最终抛 400「无法发起批改」，而正确文案应是「该提交正在批改中，请稍候」。
        # 与 `ai_grading._apply_prewrite` / `_upsert_result` 的 skip 口径一致。
        .execution_options(skip_tenant_filter=True)
        .filter(AiGradingResult.submission_id == submission_id)
        .first()
    )
    if row is not None and row.status == STATUS_PENDING:
        return {
            "queued": 0,
            "skipped": 1,
            "already_graded": 0,
            "reason": "该提交正在批改中，请稍候",
        }

    outcome = ai_grading.request_grading(
        db, [submission_id], a.school_id if a else user.school_id
    )
    if outcome["queued"] == 0:
        raise HTTPException(status_code=400, detail=outcome["reason"] or "无法发起批改")
    audit(db, user, "ai_grade_submission", target=f"提交#{submission_id}")
    db.commit()
    return outcome


def _assignment_submission_ids(db: Session, assignment_id: int) -> list[int]:
    """取某作业下全部提交 id（按 id 升序），批量批改与进度查询共用。"""
    return [
        sid
        for (sid,) in db.query(Submission.id)
        .filter(Submission.assignment_id == assignment_id)
        .order_by(Submission.id)
        .all()
    ]


def _paginate_or_all(db: Session, q, page: int | None, page_size: int | None):
    """列表分页双路径：传了 page/page_size 走分页，否则保持原全量行为。"""
    if page is not None or page_size is not None:
        # 分页路径：规范参数（page_size 上限 200，防 `?page_size=100000` 放大查询）
        page, page_size = normalize_page(page, page_size)
        rows, total = paginate(db, q, page, page_size)
    else:
        # 兼容路径：不传 page/page_size 时保持原全量行为与返回结构不变
        rows = q.all()
        total = len(rows)
    return rows, total


def ai_grade_assignment(db: Session, assignment_id: int, user: User) -> dict:
    """教师手动批改**整个作业**的全部提交（§F3 批量入口）。

    - 只批**尚无成功结果且未在批改中**的提交：已批改的、正在批改中的都跳过，
      避免重复点击白白消耗额度（后端非阻塞返回后前端按钮即复位，教师双击会二次
      投递 → 重复外呼 + 重复扣配额）；需要重批单份时走 `ai_grade_submission`。
    - 剩余额度不足时按额度截断，并在返回值里如实回报 `skipped`。

    Returns:
        ``{queued, skipped, already_graded, reason}``
    """
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="任务不存在")
    _check_teacher_assignment_access(db, user, a)

    submission_ids = _assignment_submission_ids(db, assignment_id)
    if not submission_ids:
        return {"queued": 0, "skipped": 0, "already_graded": 0, "reason": "该作业暂无提交"}

    # 一次性取回 (submission_id, status)：既排除**已成功**的，也排除**正在批改中**
    # （pending）的。只剔除 success 时，教师双击会在首次请求非阻塞返回后二次投递，
    # 对同一份提交重复外呼并重复预扣配额（平台池默认 200 次/日，连点即可烧穿）。
    graded_ids: set[int] = set()
    inflight_ids: set[int] = set()
    for sid, status in (
        db.query(AiGradingResult.submission_id, AiGradingResult.status)
        # 🔴 必须跳过租户过滤（同单份守卫）：`submission_id` 全局唯一，结果行身份与租户
        # 无关。结果行 `school_id` 为 NULL 或属他校（历史脏数据）时，当前租户读不到 ⇒
        # 已 success 的脏归属行会被重新入队 → 重复外呼 + 重复占额度。
        .execution_options(skip_tenant_filter=True)
        .filter(
            AiGradingResult.submission_id.in_(submission_ids),
            AiGradingResult.status.in_((STATUS_SUCCESS, STATUS_PENDING)),
        )
        .all()
    ):
        (graded_ids if status == STATUS_SUCCESS else inflight_ids).add(sid)
    pending_ids = [
        sid
        for sid in submission_ids
        if sid not in graded_ids and sid not in inflight_ids
    ]
    if not pending_ids:
        reason = (
            "其余提交正在批改中，请稍候" if inflight_ids else "全部提交均已批改"
        )
        return {
            "queued": 0,
            "skipped": len(submission_ids),
            "already_graded": len(graded_ids),
            "reason": reason,
        }

    outcome = ai_grading.request_grading(db, pending_ids, a.school_id)
    if outcome["queued"] == 0:
        # 无法批改（开关关闭 / 无凭证 / 额度耗尽）时如实报错，不发审计
        raise HTTPException(status_code=400, detail=outcome["reason"] or "无法发起批改")

    audit(
        db,
        user,
        "ai_grade_assignment",
        target=f"作业#{assignment_id}",
        detail=f"AI 批改 {outcome['queued']} 份",
        class_id=a.class_id,
    )
    db.commit()
    return {
        "queued": outcome["queued"],
        "skipped": outcome["skipped"] + len(graded_ids) + len(inflight_ids),
        "already_graded": len(graded_ids),
        "reason": outcome["reason"],
    }


def ai_grade_progress(db: Session, assignment_id: int, user: User) -> dict:
    """查询**整份作业**的 AI 批改进度（前端轮询用）。

    与批量触发 `ai_grade_assignment` 复用**同一套权限判据**
    （`_check_teacher_assignment_access`：本班教师或该作业创建者 / 管理员可读），不另写一套。
    纯聚合、无写操作、无外呼，可安全被前端每 2 秒轮询一次。

    `finished` 的语义是「**没有在跑的任务了**」（`pending == 0`），而**不是**
    「全部批改完」（`done == total`）：额度不足时只有部分提交被投递，其余会永远停在
    `ungraded`；若按 `done == total` 判断，进度条将永远到不了 100%，教师会误以为卡住。
    因此这里如实展示「还有 N 份未批改」，并在 `pending == 0` 时让前端停止轮询。

    Raises:
        HTTPException: 作业不存在 404；非本班且非创建者教师 403。
    """
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="任务不存在")
    _check_teacher_assignment_access(db, user, a)

    submission_ids = _assignment_submission_ids(db, assignment_id)
    progress = ai_grading.progress_for_submissions(db, submission_ids)
    progress["finished"] = progress["pending"] == 0
    return progress


# ---------------- 作业任务 ----------------
def list_assignments(
    db: Session,
    class_id: int | None,
    user: User,
    page: int | None = None,
    page_size: int | None = None,
) -> dict:
    # 学生角色：预取学生档案，用于判断是否已提交
    stu = get_student_by_account(db, user) if user.role == "student" else None
    q = db.query(Assignment)
    if user.role == "student":
        q = q.filter(Assignment.class_id == user.class_id)
    elif user.role == "teacher":
        # 教师看自己负责班级的作业，外加**自己创建**的（「创建者保留管理权」）
        q = q.filter(
            or_(
                Assignment.class_id.in_(get_teacher_class_ids(db, user.id)),
                Assignment.created_by == user.id,
            )
        )
    elif class_id:
        q = q.filter(Assignment.class_id == class_id)

    # 预加载附件，避免逐行懒加载（N+1）
    q = q.options(selectinload(Assignment.attachments)).order_by(
        Assignment.created_at.desc(), Assignment.id.desc()
    )
    rows, total = _paginate_or_all(db, q, page, page_size)

    # 批量查询：班级名 / 创建者名 / 各作业提交数 / 当前学生已提交的作业，消除逐行 db.get 与 count
    assign_ids = [a.id for a in rows]
    class_ids = {a.class_id for a in rows if a.class_id}
    creator_ids = {a.created_by for a in rows if a.created_by}
    classes = (
        {c.id: c.name for c in db.query(Classroom.id, Classroom.name).filter(Classroom.id.in_(class_ids)).all()}
        if class_ids else {}
    )
    creators = (
        {u.id: u.name for u in db.query(User.id, User.name).filter(User.id.in_(creator_ids)).all()}
        if creator_ids else {}
    )
    sub_counts = (
        dict(
            db.query(Submission.assignment_id, func.count(Submission.id))
            .filter(Submission.assignment_id.in_(assign_ids))
            .group_by(Submission.assignment_id)
            .all()
        )
        if assign_ids else {}
    )
    my_submitted_ids = set()
    if stu and assign_ids:
        my_submitted_ids = {
            aid
            for (aid,) in db.query(Submission.assignment_id)
            .filter(
                Submission.assignment_id.in_(assign_ids),
                Submission.student_id == stu.id,
            )
            .all()
        }

    items = []
    for a in rows:
        d = to_dict(a)
        d["class_name"] = classes.get(a.class_id)
        d["creator_name"] = creators.get(a.created_by)
        d["attachment_count"] = len(a.attachments)
        d["submission_count"] = sub_counts.get(a.id, 0)
        if stu:
            d["my_submitted"] = a.id in my_submitted_ids
        items.append(d)
    return {"items": items, "total": total}


def get_assignment(db: Session, assignment_id: int, user: User) -> dict:
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="任务不存在")
    _check_student_access(a, user)
    _check_teacher_assignment_access(db, user, a)
    d = to_dict(a)
    cls = db.get(Classroom, a.class_id)
    creator = db.get(User, a.created_by)
    d["class_name"] = cls.name if cls else None
    d["creator_name"] = creator.name if creator else None
    d["attachments"] = _attachments_out(a)
    # AI 学伴开关：搭车该端点返回（设计 §2.6.1 Q7，零新增端点、零额外往返 ——
    # HomeworkDetail.vue 本来就调它）。学生端据此控制学伴按钮显隐。
    # 🔴 下发值为「平台 AND 学校」合并值（docs/DESIGN-AI校级能力.md §3 D6）：
    # `is_school_ai_companion_enabled` 缺省开（无 school 级行 / `a.school_id` 为 None
    # 时恒 True），故无校级配置时合并值 ≡ 平台闸原值（行为不变）。只合平台值会导致
    # 「学生看得到按钮却提问 403」。
    # 🔴 `is_ai_companion_enabled` 内部必须走带 `skip_tenant_filter` 的 `get_global_setting`
    # （platform_settings 已实现）：学生请求带租户上下文，不加处理查全局配置
    # （`school_id IS NULL`）会**静默**落回 False 且不报错，表现为「超管开了但学生按钮
    # 死活不出现」。本字段对教师无害（同端点教师也可见，只是一个平台级布尔，不含任何
    # 学生数据/凭证），故无需按角色区分。
    from app.platform_settings import is_ai_companion_enabled
    from app.school_settings import is_school_ai_companion_enabled

    d["ai_companion_enabled"] = is_ai_companion_enabled(db) and is_school_ai_companion_enabled(db, a.school_id)
    return d


def create_assignment(db: Session, payload: dict, user: User) -> dict:
    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="标题和内容不能为空")
    class_id = payload.get("class_id")
    cls_row = db.get(Classroom, class_id)
    if not class_id or not cls_row:
        raise HTTPException(status_code=400, detail="请选择下发班级")
    # 毕业限制：毕业班级不可再布置作业
    ensure_class_operable(db, class_id)
    # 教师只能给自己负责的班级布置作业
    if not is_any_admin(user) and not is_teacher_class_owner(db, user.id, class_id):
        raise HTTPException(status_code=403, detail="只能给自己负责的班级布置作业")

    a = Assignment(
        title=title,
        description=payload.get("description", ""),
        content=content,
        deadline=payload.get("deadline"),
        created_by=user.id,
        class_id=class_id,
        # 租户归属必须显式继承班级：超管（school_id=None）上下文 before_flush
        # 不回填，落 NULL 会导致该作业对所有租户都不可见。
        school_id=cls_row.school_id,
        short_name=payload.get("short_name") or title,
    )
    _sync_attachments(a, payload.get("attachments"))
    db.add(a)
    audit(db, user, "create_assignment", target=f"布置作业", class_id=class_id)
    db.commit()
    db.refresh(a)
    d = to_dict(a)
    d["attachments"] = _attachments_out(a)
    return d


def update_assignment(db: Session, assignment_id: int, payload: dict, user: User) -> dict:
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="任务不存在")
    if a.created_by != user.id and not is_any_admin(user):
        raise HTTPException(status_code=403, detail="只能编辑自己创建的任务")
    for field in ("title", "description", "content", "deadline", "short_name"):
        if field in payload and payload[field] is not None:
            setattr(a, field, payload[field])
    if "attachments" in payload:
        _sync_attachments(a, payload["attachments"])
    if payload.get("class_id") and payload["class_id"] != a.class_id:
        new_cid = payload["class_id"]
        if not db.get(Classroom, new_cid):
            raise HTTPException(status_code=400, detail="目标班级不存在")
        # 毕业限制：不可将作业转移到已毕业班级
        ensure_class_operable(db, new_cid)
        # 教师只能将作业转移到自己负责的班级
        if not is_any_admin(user) and not is_teacher_class_owner(db, user.id, new_cid):
            raise HTTPException(status_code=403, detail="只能将任务转移到自己负责的班级")
        a.class_id = new_cid
    audit(db, user, "update_assignment", target=f"作业#{assignment_id}", class_id=a.class_id)
    db.commit()
    db.refresh(a)
    d = to_dict(a)
    d["attachments"] = _attachments_out(a)
    return d


def delete_assignment(db: Session, assignment_id: int, user: User) -> dict:
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="任务不存在")
    if a.created_by != user.id and not is_any_admin(user):
        raise HTTPException(status_code=403, detail="只能删除自己创建的任务")
    _remove_upload_files([att.filepath for att in a.attachments])
    db.delete(a)
    audit(db, user, "delete_assignment", target=f"作业#{assignment_id}", class_id=a.class_id)
    db.commit()
    return {"ok": True}


# ---------------- 作业提交 ----------------
def list_submissions(
    db: Session,
    assignment_id: int,
    user: User,
    page: int | None = None,
    page_size: int | None = None,
) -> dict:
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="任务不存在")
    _check_student_access(a, user)
    _check_teacher_assignment_access(db, user, a)
    q = db.query(Submission).filter(Submission.assignment_id == assignment_id)
    if user.role == "student":
        stu = get_student_by_account(db, user)
        if not stu:
            return {"items": [], "total": 0}
        q = q.filter(Submission.student_id == stu.id)
    q = q.order_by(Submission.created_at.desc(), Submission.id.desc())
    rows, total = _paginate_or_all(db, q, page, page_size)
    # 批量查询，避免 N+1（姓名/学号 + 头像各一次）
    stu_map = batch_student_map(db, [s.student_id for s in rows])
    avatar_map = batch_student_avatar_map(db, [s.student_id for s in rows])
    sid_list = [s.id for s in rows]
    excellent_ids = {
        e.submission_id
        for e in db.query(ExcellentWork.submission_id)
        .filter(ExcellentWork.submission_id.in_(sid_list))
        .all()
    }
    items = []
    ai_map = _ai_status_map(db, sid_list)
    for s in rows:
        d = to_dict(s)
        info = stu_map.get(s.student_id)
        d["student_name"] = info["name"] if info else None
        d["student_avatar"] = avatar_map.get(s.student_id)
        d["is_excellent"] = s.id in excellent_ids
        # AI 批改状态：教师端「AI 批改」按钮的结果反馈（批改中 / 已批改 / 未批改）
        ai = ai_map.get(s.id) or {}
        d["ai_grading_status"] = ai.get("status")
        d["ai_score"] = ai.get("score")
        d["ai_excellent_candidate"] = ai.get("is_excellent_candidate", False)
        items.append(d)
    return {"items": items, "total": total}


def unsubmitted_students(db: Session, assignment_id: int, user: User) -> dict:
    """未交名单：作业下发班级中「在籍但尚未提交」的学生。

    统计口径：
    - **应提交** = 作业下发班级下的全部学生，**排除已退学**（`is_dropped_out`）；
    - **已提交** = 该作业存在 Submission 记录的学生（跨班提交等异常数据只统计本班在籍部分）；
    - **未交** = 应提交 − 已提交。

    Args:
        db: 数据库会话。
        assignment_id: 作业任务 id。
        user: 当前用户（教师仅能查看自己负责班级的作业）。

    Returns:
        ``{ assignment_id, assignment_title, total, submitted_count,
             unsubmitted_count, items: [{id, name, student_no}] }``
    """
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="任务不存在")
    # 教师只能查看自己负责班级的作业，管理员/超管不受限
    _check_teacher_assignment_access(db, user, a)

    students = (
        db.query(Student)
        .filter(Student.class_id == a.class_id, Student.is_dropped_out.is_(False))
        .order_by(Student.student_no)
        .all()
    )
    student_ids = {s.id for s in students}

    # 只取一列，避免加载完整 Submission 对象
    submitted_ids = {
        sid
        for (sid,) in db.query(Submission.student_id)
        .filter(Submission.assignment_id == assignment_id)
        .all()
    }

    missing = [s for s in students if s.id not in submitted_ids]

    return {
        "assignment_id": a.id,
        "assignment_title": a.title,
        "total": len(students),
        "submitted_count": len(student_ids & submitted_ids),
        "unsubmitted_count": len(missing),
        "items": [
            {"id": s.id, "name": s.name, "student_no": s.student_no}
            for s in missing
        ],
    }


def get_submission(db: Session, submission_id: int, user: User) -> dict:
    """获取提交详情（含完整内容 + 教师点评列表）。"""
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(status_code=404, detail="提交不存在")
    a = db.get(Assignment, s.assignment_id)
    _check_student_access(a, user)
    _check_teacher_assignment_access(db, user, a)
    if user.role == "student":
        stu_me = get_student_by_account(db, user)
        if not stu_me or s.student_id != stu_me.id:
            raise HTTPException(status_code=403, detail="无权查看该提交")

    d = to_dict(s)
    stu = db.get(Student, s.student_id)
    d["student_name"] = stu.name if stu else None
    d["student_avatar"] = get_student_avatar(db, stu)
    # 作业标题：学生端详情页标题与教师端面包屑都要用，缺了会退化成「作业提交」占位文案
    d["assignment_title"] = a.title if a else None
    # 评优信息：是否优秀 + 评选评语（note），供学生端详情展示
    excellent = (
        db.query(ExcellentWork).filter(ExcellentWork.submission_id == submission_id).first()
    )
    d["is_excellent"] = excellent is not None
    d["excellent_id"] = excellent.id if excellent else None
    d["excellent_note"] = excellent.note if excellent else None
    comments = (
        db.query(SubmissionComment)
        .filter(SubmissionComment.submission_id == submission_id)
        .order_by(SubmissionComment.id.asc())
        .all()
    )
    comment_items = []
    for c in comments:
        cd = to_dict(c)
        t = db.get(User, c.teacher_id)
        cd["teacher_name"] = t.name if t else None
        comment_items.append(cd)
    d["comments"] = comment_items
    # AI 批改结果与教师评语并列展示、互不覆盖；学生侧仅本人可见
    # （本函数上方已校验：学生只能访问自己的提交）
    ai_result = (
        db.query(AiGradingResult)
        # 上面已校验访问权限；结果行按全局唯一的 submission_id 1:1 对应，
        # 带租户过滤只会把归属异常的历史行藏起来（教师看到「未批改」）。
        .execution_options(skip_tenant_filter=True)
        .filter(AiGradingResult.submission_id == submission_id)
        .first()
    )
    d["ai_grading"] = _ai_grading_out(ai_result, for_student=(user.role == "student"))
    return d


def add_submission_comment(db: Session, submission_id: int, payload: dict, user: User) -> dict:
    """教师对提交添加点评（含可选评分）。"""
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(status_code=404, detail="提交不存在")
    # 教师只能点评自己班级的提交
    _check_teacher_assignment_access(db, user, db.get(Assignment, s.assignment_id))
    # 退学/毕业限制
    _ensure_submission_operable(db, s)
    content = (payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="点评内容不能为空")
    score = payload.get("score")
    if score is not None:
        # 类型防线：路由层已由 `SubmissionCommentCreate.score: int | None` 收成 422，
        # 这里再挡一次是因为本函数可被内部直接调用 —— 历史上 `int("abc")` 抛 ValueError
        # 未捕获 ⇒ 500（见 docs/REVIEW-2026-09-25-code-audit.md P2-C）。
        # 注意 `bool` 是 `int` 的子类，必须显式排除，否则 True 会被当成 1 分写库。
        if isinstance(score, bool):
            raise HTTPException(status_code=400, detail="评分需为 0-100 的整数")
        try:
            score = int(score)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="评分需为 0-100 的整数")
        if not 0 <= score <= 100:
            raise HTTPException(status_code=400, detail="评分需在 0-100 之间")
    c = SubmissionComment(
        submission_id=submission_id,
        teacher_id=user.id,
        # 同 mark_excellent：归属由「提交所属学校」决定，避免平台超管操作落成 NULL
        school_id=s.school_id,
        content=content,
        score=score,
    )
    db.add(c)
    stu = db.get(Student, s.student_id)
    stu_name = stu.name if stu else ""
    audit(db, user, "add_submission_comment", target=f"点评-{stu_name}", student_id=s.student_id)
    db.commit()
    db.refresh(c)
    cd = to_dict(c)
    cd["teacher_name"] = user.name
    return cd


def delete_submission_comment(db: Session, submission_id: int, comment_id: int, user: User) -> dict:
    """删除点评（仅点评者本人或管理员）。"""
    c = db.get(SubmissionComment, comment_id)
    if not c or c.submission_id != submission_id:
        raise HTTPException(status_code=404, detail="点评不存在")
    if not is_any_admin(user) and c.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="无权删除该点评")
    # 退学/毕业限制 + 教师只能操作自己班级的提交
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(status_code=404, detail="记录不存在")
    _check_teacher_assignment_access(db, user, db.get(Assignment, s.assignment_id))
    _ensure_submission_operable(db, s)
    db.delete(c)
    stu = db.get(Student, s.student_id) if s else None
    stu_name = stu.name if stu else ""
    audit(db, user, "delete_submission_comment", target=f"删除点评-{stu_name}", student_id=s.student_id)
    db.commit()
    return {"ok": True}


def submit(db: Session, assignment_id: int, payload: dict, user: User) -> dict:
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="任务不存在")
    _check_student_access(a, user)
    # 学生档案定位（submissions.student_id 指向 students.id）
    stu = get_student_by_account(db, user)
    if not stu:
        raise HTTPException(status_code=404, detail="学生档案不存在")
    content = (payload.get("content") or "").strip()
    filepath = payload.get("filepath")
    filename = payload.get("filename")
    if filepath:
        # 第二道防线：路由层已由 `SubmissionCreate` 校验（422），这里兜住内部直调，
        # 保证非法路径**永不落库**（落库即成为重交时的删除目标，见 P0-A）。
        ensure_upload_path(filepath)
    if not content and not filepath:
        raise HTTPException(status_code=400, detail="请填写作业内容或上传文件")

    existing = (
        db.query(Submission)
        .filter(Submission.assignment_id == assignment_id, Submission.student_id == stu.id)
        .first()
    )
    if existing:
        existing.content = content
        new_filepath = filepath or existing.filepath
        # 替换附件时清理旧文件，避免泄漏
        if new_filepath != existing.filepath:
            _remove_upload_files([existing.filepath])
        existing.filepath = new_filepath
        existing.filename = filename or existing.filename
        db.commit()
        db.refresh(existing)
        # AI 批改是教师手动触发的（§F3），提交接口不再外呼；但学生重交后旧结果已
        # 不再对应当前内容 —— 留着会让师生看到「已批改」，实际批的是旧版本。
        # 因此重交即作废旧结果，教师可再次点击「AI 批改」重新批改。
        _discard_ai_grading(db, existing.id)
        return to_dict(existing)

    s = Submission(
        assignment_id=assignment_id,
        student_id=stu.id,
        content=content,
        filename=filename,
        filepath=filepath,
    )
    db.add(s)
    try:
        db.commit()
    except IntegrityError:
        # 并发兜底：上面的「先查后改」在**首次**提交并发时可能双双查不到、各插一行。
        # 数据库唯一索引 `uq_submission_assignment_student` 会拦下第二次插入；
        # 此时说明另一个请求已经建好该提交，因此退化为「更新」而不是把 409 抛给用户
        # （双击提交按钮不应报错）。
        db.rollback()
        existing = (
            db.query(Submission)
            .filter(
                Submission.assignment_id == assignment_id,
                Submission.student_id == stu.id,
            )
            .first()
        )
        if existing is None:
            raise
        existing.content = content
        if filepath:
            existing.filepath = filepath
            existing.filename = filename or existing.filename
        db.commit()
        db.refresh(existing)
        _discard_ai_grading(db, existing.id)
        return to_dict(existing)
    db.refresh(s)
    # 提交接口不做任何 AI 外呼：批改由教师在「上机作业管理」手动触发（§F3）
    return to_dict(s)


def my_submissions(db: Session, user: User) -> dict:
    stu = get_student_by_account(db, user)
    if not stu:
        return {"items": [], "total": 0}
    rows = (
        db.query(Submission)
        .filter(Submission.student_id == stu.id)
        .order_by(Submission.created_at.desc())
        .all()
    )
    # 批量查询作业标题与评优结果，消除逐行 db.get / count 的 N+1
    assign_ids = {s.assignment_id for s in rows if s.assignment_id}
    assigns = (
        {a.id: a.title for a in db.query(Assignment.id, Assignment.title).filter(Assignment.id.in_(assign_ids)).all()}
        if assign_ids else {}
    )
    sub_ids = [s.id for s in rows]
    excellent_ids = (
        {
            sid
            for (sid,) in db.query(ExcellentWork.submission_id)
            .filter(ExcellentWork.submission_id.in_(sub_ids))
            .all()
        }
        if sub_ids else set()
    )
    # AI 批改状态（学生端列表展示「批改中 / 已批改」）
    ai_map = _ai_status_map(db, sub_ids)
    items = []
    for s in rows:
        d = to_dict(s)
        d["assignment_title"] = assigns.get(s.assignment_id)
        d["is_excellent"] = s.id in excellent_ids
        d["ai_grading_status"] = (ai_map.get(s.id) or {}).get("status")
        items.append(d)
    return {"items": items, "total": len(items)}


# ---------------- 优秀作品 ----------------
def _find_excellent_of_submission(db: Session, submission_id: int) -> ExcellentWork | None:
    """按 `submission_id` 查优秀作品行，**忽略租户过滤**。

    为什么必须忽略租户过滤：`excellent_works.submission_id` 上的唯一索引是**全局**的，
    不随 `school_id` 变化。若「是否已入选」的预检走租户过滤，则
    `school_id` 为 NULL 或属于其他学校的行查不出来，插入时却照样撞唯一键 ——
    用户拿到的是 409「数据冲突：已存在重复记录」这种无法自救的提示，
    而不是「该作品已入选优秀」这种可理解的提示。
    预检与唯一索引必须同口径，故这里统一用 `skip_tenant_filter`。

    调用方务必要先完成**租户可见性 + 归属**校验（`db.get(Submission, ...)` 是带租户过滤的），
    本函数只解决「看不见却撞键」的口径问题，不承担鉴权。
    """
    return (
        db.query(ExcellentWork)
        .execution_options(skip_tenant_filter=True)
        .filter(ExcellentWork.submission_id == submission_id)
        .first()
    )


def mark_excellent(db: Session, submission_id: int, payload: dict, user: User) -> dict:
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(status_code=404, detail="提交不存在")
    # 教师只能评自己班级的提交为优秀
    _check_teacher_assignment_access(db, user, db.get(Assignment, s.assignment_id))
    # 退学/毕业限制
    _ensure_submission_operable(db, s)
    if _find_excellent_of_submission(db, submission_id):
        raise HTTPException(status_code=400, detail="该作品已入选优秀")
    e = ExcellentWork(
        submission_id=submission_id,
        selected_by=user.id,
        # 归属取「提交所属学校」而非操作者：平台超管的 school_id 为 NULL，
        # 交给 ORM 自动填充会落成 NULL —— 该行随后对**所有**学校都不可见
        # （列表/详情/学生端全部查不到），而唯一索引仍会拦住重复插入，
        # 形成「看不见却撞键」的死局。写入方的 school_id 必须由业务归属决定。
        school_id=s.school_id,
        note=payload.get("note", ""),
        # 教师确认 AI 推荐时标记来源，便于区分人工评选与 AI 推荐（PRD §6 F4）
        source="ai_recommended" if payload.get("from_ai") else "manual",
    )
    db.add(e)
    audit(db, user, "mark_excellent", target=f"优秀-提交#{submission_id}", student_id=s.student_id)
    db.commit()
    db.refresh(e)
    return to_dict(e)


def unmark_excellent(db: Session, submission_id: int, user: User) -> dict:
    # 先做租户可见性 + 归属校验（`db.get(Submission)` 带租户过滤，跨校直接 404），
    # 再以全局口径取优秀作品行 —— 顺序不能反，否则「查不到提交」会绕过权限校验。
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(status_code=404, detail="提交不存在")
    _check_teacher_assignment_access(db, user, db.get(Assignment, s.assignment_id))
    _ensure_submission_operable(db, s)
    e = _find_excellent_of_submission(db, submission_id)
    if e:
        db.delete(e)
        audit(db, user, "unmark_excellent", target=f"取消优秀-提交#{submission_id}", student_id=s.student_id)
        db.commit()
    return {"ok": True}


def list_excellent(db: Session, page: int, page_size: int, user: User) -> dict:
    q = select(ExcellentWork)
    if user.role == "student":
        # 学生仅查看本班作业的优秀作品
        q = (
            q.join(Submission, ExcellentWork.submission_id == Submission.id)
            .join(Assignment, Submission.assignment_id == Assignment.id)
            .where(Assignment.class_id == user.class_id)
        )
    elif user.role == "teacher":
        # 教师仅查看自己班级的优秀作品
        q = (
            q.join(Submission, ExcellentWork.submission_id == Submission.id)
            .join(Assignment, Submission.assignment_id == Assignment.id)
            .where(Assignment.class_id.in_(get_teacher_class_ids(db, user.id)))
        )
    # ⚠️ 必须规范分页参数：本函数此前是全项目**唯一**漏了 normalize_page 的列表接口，
    # 因此 `?page_size=100000` 会原样落到 LIMIT，成为放大查询的入口（其余列表接口
    # 都已在 service 层调用 normalize_page，上限 200）。
    page, page_size = normalize_page(page, page_size)
    q = q.order_by(ExcellentWork.created_at.desc())
    rows, total = paginate(db, q, page, page_size)
    if not rows:
        return {"items": [], "total": total}

    # 批量查询所有关联对象，避免 N+1
    sub_ids = [e.submission_id for e in rows]
    subs = {s.id: s for s in db.query(Submission).filter(Submission.id.in_(sub_ids)).all()}
    assign_ids = {s.assignment_id for s in subs.values() if s.assignment_id}
    assigns = {a.id: a for a in db.query(Assignment).filter(Assignment.id.in_(assign_ids)).all()} if assign_ids else {}
    stu_ids = {s.student_id for s in subs.values() if s.student_id}
    students = {st.id: st for st in db.query(Student).filter(Student.id.in_(stu_ids)).all()} if stu_ids else {}
    avatar_map = batch_student_avatar_map(db, stu_ids)
    cls_ids = {a.class_id for a in assigns.values() if a.class_id}
    classes = {c.id: c for c in db.query(Classroom).filter(Classroom.id.in_(cls_ids)).all()} if cls_ids else {}
    comment_counts = dict(
        db.query(WorkComment.excellent_id, func.count(WorkComment.id))
        .filter(WorkComment.excellent_id.in_([e.id for e in rows]))
        .group_by(WorkComment.excellent_id)
        .all()
    )

    items = []
    for e in rows:
        s = subs.get(e.submission_id)
        if not s:
            continue
        a = assigns.get(s.assignment_id)
        stu = students.get(s.student_id)
        cls = classes.get(a.class_id) if a else None
        items.append(
            {
                "id": e.id,
                "note": e.note,
                "created_at": e.created_at,
                "submission": to_dict(s),
                "assignment_title": a.title if a else None,
                "assignment_id": a.id if a else None,
                "student_name": stu.name if stu else None,
                "student_avatar": avatar_map.get(s.student_id),
                "class_name": cls.name if cls else None,
                "comment_count": comment_counts.get(e.id, 0),
            }
        )
    return {"items": items, "total": total}


def get_excellent(db: Session, excellent_id: int, user: User) -> dict:
    e = db.get(ExcellentWork, excellent_id)
    if not e:
        raise HTTPException(status_code=404, detail="作品不存在")
    s = db.get(Submission, e.submission_id)
    a = db.get(Assignment, s.assignment_id) if s else None
    stu = db.get(Student, s.student_id) if s else None
    cls = db.get(Classroom, a.class_id) if a else None
    comments = (
        db.query(WorkComment)
        .filter(WorkComment.excellent_id == excellent_id)
        .order_by(WorkComment.created_at.asc())
        .all()
    )
    comment_items = []
    for c in comments:
        cd = to_dict(c)
        cu = db.get(User, c.user_id)
        cd["user_name"] = cu.name if cu else None
        cd["user_avatar"] = cu.avatar if cu else None
        comment_items.append(cd)
    # 聚合该提交的「批改评语」（submission_comments），与评优时的 note 打通展示
    teacher_comments = []
    if s:
        tcs = (
            db.query(SubmissionComment)
            .filter(SubmissionComment.submission_id == s.id)
            .order_by(SubmissionComment.id.asc())
            .all()
        )
        for tc in tcs:
            tcd = to_dict(tc)
            t = db.get(User, tc.teacher_id)
            tcd["teacher_name"] = t.name if t else None
            teacher_comments.append(tcd)
    # AI 批改意见：优秀作品详情页同样展示（与提交详情同口径；学生侧不返回 error）
    ai_result = None
    if s:
        ai_result = (
            # 同上：结果行按全局唯一的 submission_id 定位，不参与租户过滤
            db.query(AiGradingResult)
            .execution_options(skip_tenant_filter=True)
            .filter(AiGradingResult.submission_id == s.id)
            .first()
        )
    return {
        "id": e.id,
        "note": e.note,
        "created_at": e.created_at,
        "submission": to_dict(s),
        "assignment_title": a.title if a else None,
        "assignment_id": a.id if a else None,
        "student_name": stu.name if stu else None,
        "student_avatar": get_student_avatar(db, stu),
        "class_name": cls.name if cls else None,
        "comments": comment_items,
        "teacher_comments": teacher_comments,
        "ai_grading": _ai_grading_out(ai_result, for_student=(user.role == "student")),
    }


def add_comment(db: Session, excellent_id: int, payload: dict, user: User) -> dict:
    ew = db.get(ExcellentWork, excellent_id)
    if not ew:
        raise HTTPException(status_code=404, detail="作品不存在")
    content = (payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="评论内容不能为空")
    c = WorkComment(
        excellent_id=excellent_id,
        user_id=user.id,
        # 同上：归属继承作品行，平台超管互评时不会落成 NULL
        school_id=ew.school_id,
        content=content,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    d = to_dict(c)
    d["user_name"] = user.name
    d["user_avatar"] = user.avatar
    return d
