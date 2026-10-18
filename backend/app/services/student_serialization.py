"""学生序列化公共出口：`student_out` / `students_out`。

从 `students_service` 提取而来。原先以 `_student_out` / `_students_out` 的**私有**名义
被 `mobile_service`、`workbench/profile_service` 跨模块引用 —— 下划线前缀会让改动者
误以为没有外部调用方。本模块把这份能力提升为显式公共 API：

- **单一职责**：只做「Student ORM → 对外字典」（补 `class_name` / `avatar`）；
- **批量优先**：`students_out` 一次查班级名 + 一次查头像，避免 N+1；
- **不含业务判断**：权限、班级过滤、可见性由调用方负责。
"""
from sqlalchemy.orm import Session

from app.audit import batch_student_avatar_map
from app.models import Classroom, Student
from app.utils import to_dict


def students_out(db: Session, rows: list) -> list:
    """批量序列化学生：一次查班级名 + 一次查头像，避免 N+1。"""
    if not rows:
        return []
    class_ids = {s.class_id for s in rows if s.class_id}
    class_map = (
        {c.id: c.name for c in db.query(Classroom).filter(Classroom.id.in_(class_ids)).all()}
        if class_ids
        else {}
    )
    avatar_map = batch_student_avatar_map(db, [s.id for s in rows])
    items = []
    for s in rows:
        d = to_dict(s)
        d["class_name"] = class_map.get(s.class_id)
        d["avatar"] = avatar_map.get(s.id)
        items.append(d)
    return items


def student_out(db: Session, s: Student) -> dict:
    """单个学生序列化（含班级名 + 头像）。"""
    return students_out(db, [s])[0]
