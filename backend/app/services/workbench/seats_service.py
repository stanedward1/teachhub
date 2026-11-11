"""座位表布局业务逻辑：查询、保存。"""
import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit import audit
from app.models import Seat, Student
from app.permissions import (
    ensure_class_operable,
    is_any_admin,
    is_teacher_class_owner,
)
from app.schemas import SeatSave


def _collect_student_ids(layout) -> set:
    """拍平二维布局，收集非空的座位 id（`None` = 空位，直接跳过）。"""
    ids = set()
    for row in layout or []:
        # 兼容扁平数组（历史行可能存成 [1, 2, 3]）与二维数组（[[1, 2], [3]]）
        for raw in row if isinstance(row, (list, tuple)) else [row]:
            if raw is not None:
                ids.add(raw)
    return ids


def _ensure_students_of_class(db: Session, class_id: int, layout) -> None:
    """座位布局里的学生必须都属于 `class_id`，否则 400。

    为什么必须在**写库前**校验：前端切班是连发两次请求（读布局、读名单），
    没有请求序号时，先切 A（慢）、再切 B，A 班名单会最后落到页面上；此时保存就是
    「B 的 class_id + A 的学生」。若这里照单全收，`seats.layout` 会被直接覆盖成
    A 班学生 —— 座位表是纯覆盖写，原布局无法从接口恢复（RBT-101）。

    校验放在持久层而不是只在前端加守卫：任何调用方（含将来的批量导入、脚本）都绕不过去。
    """
    ids = _collect_student_ids(layout)
    if not ids:
        # 空布局是合法用法（清空/从未排座），不查库
        return
    # 只把整数 id 送进 SQL：`id IN ('abc')` 在 MySQL 里会被隐式转成 0，
    # 查不到但也不报错，会把「布局里有垃圾值」变成静默接受。`bool` 是 int 子类，排除。
    numeric = {i for i in ids if isinstance(i, int) and not isinstance(i, bool)}
    invalid = ids - numeric
    owned = set()
    if numeric:
        owned = {
            sid
            for (sid,) in db.query(Student.id).filter(
                Student.class_id == class_id, Student.id.in_(numeric)
            )
        }
    unknown = (numeric - owned) | invalid
    if unknown:
        # key=str 兼顾历史脏数据里的字符串 id，避免排序时 TypeError
        sample = ", ".join(sorted((str(i) for i in unknown), key=str)[:10])
        raise HTTPException(
            status_code=400,
            detail=(
                f"座位布局中有 {len(unknown)} 名学生不属于该班级（id: {sample}），"
                "请重新选择班级后再保存"
            ),
        )


def get_seat(db: Session, user, class_id: int) -> dict:
    """读取班级座位表（无记录时返回默认布局）。"""
    if not is_any_admin(user):
        if not is_teacher_class_owner(db, user.id, class_id):
            raise HTTPException(status_code=403, detail="无权查看该班级座位表")
    s = db.query(Seat).filter(Seat.class_id == class_id).first()
    if not s:
        return {"layout": [], "columns": 6}
    layout = []
    if s.layout:
        try:
            layout = json.loads(s.layout)
        except (json.JSONDecodeError, TypeError):
            layout = []
    return {"layout": layout, "columns": s.columns}


def save_seat(db: Session, user, payload: SeatSave) -> dict:
    """保存班级座位表（不存在则新建）。"""
    class_id = payload.class_id
    # 复用返回的 Classroom 以继承其 school_id
    classroom = ensure_class_operable(db, class_id)
    if not is_any_admin(user):
        if not is_teacher_class_owner(db, user.id, class_id):
            raise HTTPException(status_code=403, detail="无权修改该班级座位表")
    # 布局只能包含本班学生：否则会把别的班名单写进本班座位表并覆盖原布局（RBT-101）
    _ensure_students_of_class(db, class_id, payload.layout)
    s = db.query(Seat).filter(Seat.class_id == class_id).first()
    if not s:
        s = Seat(
            class_id=class_id,
            # 显式继承父资源（班级）的租户归属，避免超管上下文下 school_id 落 NULL
            school_id=classroom.school_id,
        )
        db.add(s)
    elif s.school_id is None:
        # 顺带修复历史脏行：school_id 落 NULL 的行在全租户下都不可见
        s.school_id = classroom.school_id
    s.layout = json.dumps(payload.layout, ensure_ascii=False)
    s.columns = payload.columns
    audit(db, user, "save_seat", target=f"保存座位表")
    db.commit()
    return {"ok": True}
