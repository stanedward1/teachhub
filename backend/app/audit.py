"""批量查询与操作审计辅助函数。

- 批量查询：消除列表接口的 N+1 问题（一次 IN 查询，替代循环内逐条 db.get）。
- 审计：关键写操作记录到 operation_logs 表。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Classroom, OperationLog, Student, User
from app.utils import to_dict


# ---------------- 审计 action 常量（集中定义，避免散落字面量导致检索不一致） ----------------
# AI 学伴教师侧查看动作。审计日志的首要消费方式是**检索/过滤**与**按 action 聚合**
# （`/admin/audit-logs`、`admin_service.audit_log_stats`），故列表与详情用**两个独立
# action**（而非「统一 action + detail 区分 scope」）—— 后者会让「按 action 精确过滤 /
# 统计查看次数」退化为文本模糊匹配，无法建索引、无法可靠聚合。
# 设计依据：docs/DESIGN-AI学伴.md §14.5 / §18.3。
AUDIT_COMPANION_VIEW_LIST = "companion_view_list"
AUDIT_COMPANION_VIEW_DETAIL = "companion_view_detail"

# 校级 AI 能力配置变更（超管专用端点，docs/DESIGN-AI校级能力.md §3 D5 / T04）。
# detail 只记变更的 key 列表，**不记配置值**（与凭证审计同哲学：审计可检索、不敏感）。
AUDIT_UPDATE_SCHOOL_AI_SETTINGS = "update_school_ai_settings"


def active_student_id_query(db: Session):
    """在籍（未退学）学生 id 子查询，供 `Model.student_id.in_(...)` 过滤使用。

    🔴 返回 ``select()`` 而非 ``Query``（2026-11-04）：``in_(Query)`` 会触发
    ``SADeprecationWarning: Coercing Query object into a select()``，SQLAlchemy 2.1 起不再
    接受。全部调用点都只把它当子查询用（``.in_(...)``），换成 ``select()`` 语义完全一致。
    """
    return select(Student.id).where(Student.is_dropped_out.is_(False))


def active_classroom_id_query(db: Session):
    """未毕业班级 id 子查询，供 `Model.class_id.in_(...)` 过滤使用（同上：返回 ``select()``）。"""
    return select(Classroom.id).where(Classroom.is_graduated.is_(False))


def batch_student_avatar_map(db: Session, student_ids) -> dict:
    """{student_id: avatar}，一次 join 查询避免 N+1。

    头像统一存于 users.avatar（学生登录账号）。🔴 必须按**硬外键**
    ``users.student_id == students.id`` 关联（RBT-65）：旧实现用
    ``(class_id, name)`` 软关联，同班同名的两名学生会被映射到**同一个**账号上，
    B 的头像列显示的是 A 的照片。

    历史账号（``student_id`` 尚未回填）逐条回落到 ``get_student_avatar`` —— 那里有
    与 ``get_account_of_student`` 同源的归属校验，且这类行在实测库里为 0 条
    （2026-11-04：37 个学生账号、NULL 0 条），N+1 只发生在真正的历史数据上。
    """
    ids = [i for i in (student_ids or []) if i is not None]
    if not ids:
        return {}
    rows = (
        db.query(Student.id, User.avatar)
        .join(User, User.student_id == Student.id)
        .filter(Student.id.in_(ids))
        .all()
    )
    result = {sid: avatar for sid, avatar in rows}
    missing = [i for i in ids if i not in result]
    if missing:
        # 延迟导入：`app.permissions` 反向不依赖本模块，此处仅为把循环 import 的可能
        # 彻底挡在函数体内（audit 被 models 之外的层次广泛引用）。
        from app.permissions import get_student_avatar

        for s in db.query(Student).filter(Student.id.in_(missing)).all():
            avatar = get_student_avatar(db, s)
            if avatar:
                result[s.id] = avatar
    return result


def batch_student_map(db: Session, student_ids) -> dict:
    """返回 {student_id: {"name": ..., "no": ...}}，一次查询。"""
    ids = [i for i in (student_ids or []) if i is not None]
    if not ids:
        return {}
    rows = db.query(Student).filter(Student.id.in_(ids)).all()
    return {s.id: {"name": s.name, "no": s.student_no} for s in rows}


def batch_user_map(db: Session, user_ids) -> dict:
    """返回 {user_id: {"name": ..., "avatar": ...}}，一次查询。"""
    ids = [i for i in (user_ids or []) if i is not None]
    if not ids:
        return {}
    rows = db.query(User).filter(User.id.in_(ids)).all()
    return {u.id: {"name": u.name, "avatar": u.avatar} for u in rows}


def attach_student(db: Session, d: dict, student_id) -> dict:
    """单个对象填充学生姓名/学号（配合 batch_student_map 使用）。"""
    if student_id:
        info = batch_student_map(db, [student_id]).get(student_id)
        if info:
            d["student_name"] = info["name"]
            d["student_no"] = info["no"]
    return d


def serialize_list_with_students(db: Session, rows, id_attr: str = "student_id"):
    """列表序列化：一次批量查询学生信息，避免 N+1。

    返回 [dict, ...]，每项已含 student_name / student_no。
    """
    ids = [getattr(r, id_attr, None) for r in rows]
    smap = batch_student_map(db, ids)
    items = []
    for r in rows:
        d = to_dict(r)
        sid = getattr(r, id_attr, None)
        if sid in smap:
            d["student_name"] = smap[sid]["name"]
            d["student_no"] = smap[sid]["no"]
        items.append(d)
    return items


def audit(db: Session, user, action: str, target: str = "", detail: str = "", class_id=None, student_id=None):
    """记录一条操作审计日志（不 commit，由调用方统一提交）。

    class_id：班级/学生相关操作传入关联班级，用于班主任按班级查看审计日志；
    student_id：学生相关操作可传学生 id，函数内部自动解析其所属班级。
    """
    if class_id is None and student_id is not None:
        s = db.get(Student, student_id)
        class_id = s.class_id if s else None
    db.add(
        OperationLog(
            user_id=user.id if user else None,
            username=user.username if user else None,
            role=user.role if user else None,
            school_id=getattr(user, "school_id", None),  # 租户归属（平台超管为 None）
            action=action,
            target=target,
            detail=detail,
            class_id=class_id,
        )
    )


def student_name(db: Session, student_id) -> str:
    """根据学生 ID 获取学生姓名（用于审计日志 target 中记录操作对象）。"""
    if not student_id:
        return ""
    s = db.get(Student, student_id)
    return s.name if s else ""
