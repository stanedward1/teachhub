"""教师查看本班学生「AI 学伴」会话（只读）。

设计依据：``docs/DESIGN-AI学伴.md`` §14（增补 2）。

本模块**只承载 T03 的教师侧只读能力**：列表 + 详情两段查询与审计。
之所以单列模块而非并入 ``ai_companion.py``：``ai_companion.py`` 由 T02 实现
（学生问答链路 + 独立额度原语），教师侧是**独立的新增越权面**（§14 开头原文），
单列可避免与并行工程师冲突，也符合「一域一模块」的分层约定。

🔴 三条硬约束（不可违反）：

1. **权限口径 = 班主任 ∪ 科任**（§14.1，``get_teacher_class_ids`` / V-b/V-c），
   **不是** ``get_head_class_ids``（那是仅班主任、专用于 /admin/audit-logs）。
   列表优先复用 ``apply_teacher_student_filter``（V-d，项目注释明确「统一收口避免遗漏」）。
2. **教师侧只读**（X6）：本模块**不提供**任何写学生会话的函数。
3. **会话详情三重硬校验**（§14.2，缺一不可）：① 会话存在；② 其作业本班可访问
   （``_check_teacher_assignment_access``，V-a）；③ 该会话 ``student_id`` 落在教师
   可见班级范围内。**任不满足一律 404**（X5：不泄露会话存在性）。

多租户：会话/消息表含 ``school_id``，查询**不手写** ``school_id`` 条件（S2，由
``tenant.py`` 的 ORM 事件自动隔离）；本模块不做 ``skip_tenant_filter``。
"""
import logging

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import (
    AUDIT_COMPANION_VIEW_DETAIL,
    AUDIT_COMPANION_VIEW_LIST,
    audit,
    batch_student_avatar_map,
    batch_student_map,
    student_name,
)
from app.models import (
    AiCompanionConversation,
    AiCompanionMessage,
    Assignment,
    Student,
    User,
)
from app.pagination import paginate

logger = logging.getLogger("teachhub.ai")


def _check_teacher_assignment_access(db: Session, user: User, assignment: Assignment) -> None:
    """作业级入口校验（V-a）：仅本班可访问，管理员不受限。

    直接复用 ``homework_service._check_teacher_assignment_access``（``§14.3 V-a``，
    原文要求「🔴 不可绕过」）。该函数语义为：``assignment is None`` 直接放行、
    教师非本班 ⇒ 403、管理员不受限。这里复用**同一实现**，保证口径不漂移。
    """
    from app.services.homework_service import _check_teacher_assignment_access

    _check_teacher_assignment_access(db, user, assignment)


def list_companion_conversations(
    db: Session,
    assignment_id: int,
    user: User,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """列出**该作业下**本班学生的学伴会话（一个学生会话 = 一行）。

    Args:
        db: 数据库会话。
        assignment_id: 作业 ID。
        user: 当前教师（路由层已用 ``require_teacher_only`` 限定 role=teacher）。
        page / page_size: 分页参数（复用项目 ``pagination.normalize_page`` 同源口径）。

    Returns:
        ``{"items": [{conversation_id, student_id, student_name, student_avatar,
        class_id, turn_count, refused_count, last_active_at}], "total": int}``

    Note:
        **列表不含消息内容**（§14.2「不返回」行）：避免一次性拖出全班对话全文。
        只给「谁、问了几轮、有无拒答、最后活跃时间」。

        **审计**（§14.5 / §18.3）：列表一次覆盖多个学生，而 ``audit()`` 只接受**单个**
        ``student_id``，故列表审计**不传 student_id**，改传 ``class_id=assignment.class_id``
        （保证该条落入班主任可见范围），``detail`` 只写「返回 N 条」+ 元数据，
        **绝不写对话内容**。
    """
    from app.utils import normalize_page

    page, page_size = normalize_page(page, page_size)

    assignment = db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="任务不存在")
    # 硬校验 ①：非本班作业直接 403（V-a；同校跨班 ORM 不覆盖，必须显式校验）
    _check_teacher_assignment_access(db, user, assignment)

    stmt = (
        select(AiCompanionConversation)
        .where(AiCompanionConversation.assignment_id == assignment_id)
        # 最新活跃在前；id 单调，避免同秒并发下 created_at 不稳定
        .order_by(AiCompanionConversation.id.desc())
    )
    # 统一权限收口（V-d，§14.3 推荐优先）：按 model.student_id 过滤，教师无班级 ⇒ denied
    from app.permissions import apply_teacher_student_filter

    stmt, denied = apply_teacher_student_filter(db, user, stmt, AiCompanionConversation)
    if denied:
        rows, total = [], 0
    else:
        rows, total = paginate(db, stmt, page, page_size)

    conv_ids = [c.id for c in rows]
    student_ids = [c.student_id for c in rows]
    name_map = batch_student_map(db, student_ids)
    avatar_map = batch_student_avatar_map(db, student_ids)
    # 拒答计数：一次聚合（避免逐会话 count 的 N+1）
    refused_map: dict[int, int] = {}
    if conv_ids:
        refused_rows = (
            db.query(
                AiCompanionMessage.conversation_id,
                func.count(AiCompanionMessage.id),
            )
            .filter(
                AiCompanionMessage.conversation_id.in_(conv_ids),
                AiCompanionMessage.refused.is_(True),
            )
            .group_by(AiCompanionMessage.conversation_id)
            .all()
        )
        refused_map = {cid: int(cnt or 0) for cid, cnt in refused_rows}

    items = []
    for c in rows:
        info = name_map.get(c.student_id) or {}
        refused_count = refused_map.get(c.id, 0)
        items.append(
            {
                "conversation_id": c.id,
                "student_id": c.student_id,
                "student_name": info.get("name"),
                "student_avatar": avatar_map.get(c.student_id),
                "class_id": assignment.class_id,
                "turn_count": int(c.turn_count or 0),
                "refused_count": refused_count,
                # has_refused：前端「学伴」列用于标记是否有拒答（§14.6）
                "has_refused": refused_count > 0,
                "last_active_at": c.updated_at.isoformat() if c.updated_at else None,
            }
        )

    # 🔴 审计（列表）：不传 student_id（一次覆盖多人），改传 class_id ⇒ 必落入班主任可见范围；
    # detail 只写元数据，绝不写对话内容（会话随作业级联删除而审计不删 ⇒ 防合规矛盾，§14.5）。
    audit(
        db,
        user,
        AUDIT_COMPANION_VIEW_LIST,
        target=f"作业#{assignment_id} 学伴会话列表",
        detail=f"返回 {len(items)} 条（作业#{assignment_id}，班级#{assignment.class_id}）",
        class_id=assignment.class_id,
    )
    # audit() 自身不 commit ⇒ 与业务查询同事务提交（§18.3）
    db.commit()

    return {"items": items, "total": int(total)}


def get_companion_conversation(
    db: Session,
    conversation_id: int,
    user: User,
) -> dict:
    """取**单个会话的完整消息**（教师点进某学生后）。

    Args:
        db: 数据库会话。
        conversation_id: 会话 ID。
        user: 当前教师（role=teacher）。

    Returns:
        ``{"conversation_id", "student_id", "student_name", "assignment_id",
        "assignment_title", "messages": [{id, role, content, refused, created_at}],
        "turns"}``

    Raises:
        HTTPException: 404 —— 三重校验任一不满足（X5：不泄露会话存在性）。

    Note:
        **含学生提问原文 + AI 全文**（§14.2 明确列为 ✅）。理由：若只有元数据，教师无法
        判断学生卡在哪、学伴是否越栏，功能无价值；且登录用户已是**该班教师**（三重校验），
        与「教师能看学生提交的作业全文」同级。

        🔴 **三重硬校验**（§14.2，缺一不可）：
        ① 会话必须存在（否则 404）；
        ② 会话的 ``assignment_id`` 对应作业必须**本班可访问**（``_check_teacher_assignment_access``）；
        ③ 该会话 ``student_id`` 必须落在 ``get_teacher_class_ids`` 覆盖范围内
           （防「本班教师拿别的会话 id 试探」）。
        任一条不满足 ⇒ **404**（不返回 403，避免泄露会话存在性）。

        **审计**（§14.5 / §18.3）：详情照常传 ``student_id``（``audit()`` 内部会自动
        解析班级并填 class_id）；``detail`` 只写 ``student_name`` + ``turn_count``，
        **绝不写对话内容**（会话随作业删、审计不删 ⇒ 防「会话已删、内容残留」矛盾）。
    """
    conv = db.get(AiCompanionConversation, conversation_id)
    # 校验 ①：会话不存在 ⇒ 404（跨校亦被 ORM 过滤为「不存在」，符合 §14.4 X2）
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")

    assignment = db.get(Assignment, conv.assignment_id)
    # 校验 ②：作业本班可访问；不可访问一律以 404 收尾（X5，不泄露存在性）。
    # 注意：_check_teacher_assignment_access 会抛 403，这里**捕获后转 404**，
    # 以统一满足「会话详情越权 ⇒ 404」的红线。
    try:
        _check_teacher_assignment_access(db, user, assignment)
    except HTTPException:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 校验 ③：该学生会话必须落在教师可见班级范围内（班主任 ∪ 科任，§14.1）
    from app.permissions import get_teacher_class_ids

    class_ids = get_teacher_class_ids(db, user.id)
    student = db.get(Student, conv.student_id)
    if not class_ids or student is None or student.class_id not in class_ids:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = (
        db.query(AiCompanionMessage)
        .filter(AiCompanionMessage.conversation_id == conversation_id)
        .order_by(AiCompanionMessage.id.asc())
        .all()
    )
    items = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "refused": bool(m.refused),
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]

    # 🔴 审计（详情）：传 student_id（audit() 自动解析班级填 class_id）；
    # detail 只写元数据（学生姓名 + 轮数），绝不写对话内容。
    audit(
        db,
        user,
        AUDIT_COMPANION_VIEW_DETAIL,
        target=f"学伴会话#{conversation_id}",
        detail=(
            f"student_name={student_name(db, conv.student_id)} "
            f"turn_count={int(conv.turn_count or 0)}"
        ),
        student_id=conv.student_id,
    )
    db.commit()

    return {
        "conversation_id": conv.id,
        "student_id": conv.student_id,
        "student_name": student.name if student else None,
        "assignment_id": conv.assignment_id,
        "assignment_title": assignment.title if assignment else None,
        "messages": items,
        "turns": int(conv.turn_count or 0),
    }
