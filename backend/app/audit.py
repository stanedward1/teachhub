"""批量查询与操作审计辅助函数。

- 批量查询：消除列表接口的 N+1 问题（一次 IN 查询，替代循环内逐条 db.get）。
- 审计：关键写操作记录到 operation_logs 表。
"""
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models import Classroom, OperationLog, Student, User
from app.utils import to_dict


def active_student_id_query(db: Session):
    """在籍（未退学）学生 id 子查询，供 `Model.student_id.in_(...)` 过滤使用。"""
    return db.query(Student.id).filter(Student.is_dropped_out.is_(False))


def active_classroom_id_query(db: Session):
    """未毕业班级 id 子查询，供 `Model.class_id.in_(...)` 过滤使用。"""
    return db.query(Classroom.id).filter(Classroom.is_graduated.is_(False))


def batch_student_avatar_map(db: Session, student_ids) -> dict:
    """{student_id: avatar}，一次 join 查询避免 N+1。

    头像统一存于 users.avatar（学生登录账号），通过 class_id + name 关联到学生档案。
    """
    ids = [i for i in (student_ids or []) if i is not None]
    if not ids:
        return {}
    rows = (
        db.query(Student.id, User.avatar)
        .join(
            User,
            and_(User.class_id == Student.class_id, User.name == Student.name, User.role == "student"),
        )
        .filter(Student.id.in_(ids))
        .all()
    )
    return {sid: avatar for sid, avatar in rows}


def batch_student_login_map(db: Session, student_ids) -> dict:
    """{student_id: {"last_login_at": ..., "last_login_ip": ...}}，一次 join 避免 N+1。

    最后登录信息存于 users（学生登录账号），同样通过 class_id + name 关联到学生档案。
    未登录过或未匹配到账号的学生返回空字典项，由调用方序列化为 None。
    """
    ids = [i for i in (student_ids or []) if i is not None]
    if not ids:
        return {}
    rows = (
        db.query(Student.id, User.last_login_at, User.last_login_ip)
        .join(
            User,
            and_(User.class_id == Student.class_id, User.name == Student.name, User.role == "student"),
        )
        .filter(Student.id.in_(ids))
        .all()
    )
    return {sid: {"last_login_at": at, "last_login_ip": ip} for sid, at, ip in rows}


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
