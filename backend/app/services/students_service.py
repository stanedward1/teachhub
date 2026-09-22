"""学生基础数据业务逻辑：学校 / 班级 / 班级教师 / 学生 / 头像 / 寄宿历史 / 导出。

自 `app/routers/students.py` 迁移而来（B1 分层）。对外行为与重构前完全一致，
仅 `list_students` 的分页由「count + 分页」两次查询改为 `app.pagination.paginate`
单次查询（响应字段与顺序不变）。`_students_out` / `_student_out` 仍对外导出，
以兼容 `app/routers/mobile.py` 的既有引用。
"""
from io import BytesIO
import os
import uuid

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit, batch_student_avatar_map, batch_user_map
from app.cleanup import delete_avatar_file, purge_student_data, purge_user_data
from app.config import settings
from app.models import Classroom, ClassTeacher, School, Student, StudentBoardHistory, User
from app.pagination import paginate
from app.permissions import (
    ensure_class_operable,
    ensure_same_school,
    ensure_student_operable,
    filter_classrooms_by_teacher,
    get_student_account,
    get_teacher_class_ids,
    is_any_admin,
    is_platform_admin,
    is_student_in_teacher_classes,
    is_teacher_class_owner,
)
from app.schemas import StudentCreate, StudentUpdate
from app.security import hash_password, validate_password_strength
from app.utils import normalize_page, parse_date, to_dict

_AVATAR_DIR = settings.AVATAR_DIR
_AVATAR_MAX_SIZE = 2 * 1024 * 1024
_AVATAR_ALLOWED = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _students_out(db: Session, rows: list) -> list:
    """批量序列化学生：一次查班级名 + 一次查头像，避免 N+1。"""
    if not rows:
        return []
    class_ids = {s.class_id for s in rows if s.class_id}
    class_map = (
        {c.id: c.name for c in db.query(Classroom).filter(Classroom.id.in_(class_ids)).all()}
        if class_ids else {}
    )
    avatar_map = batch_student_avatar_map(db, [s.id for s in rows])
    items = []
    for s in rows:
        d = to_dict(s)
        d["class_name"] = class_map.get(s.class_id)
        d["avatar"] = avatar_map.get(s.id)
        items.append(d)
    return items


def _student_out(db: Session, s: Student) -> dict:
    """单个学生序列化（含班级名 + 头像）。"""
    return _students_out(db, [s])[0]


# ---------------- 学校 ----------------
def list_schools(db: Session, user: User) -> dict:
    """学校列表：平台超管看全部，其他角色仅能看到自己所属学校。"""
    q = db.query(School)
    if not is_platform_admin(user):
        q = q.filter(School.id == user.school_id)
    rows = q.order_by(School.id).all()
    # 一次聚合查询各校学生数/班级数，避免逐校 count 的 N+1
    school_ids = [sc.id for sc in rows]
    student_counts = (
        dict(db.query(Student.school_id, func.count()).filter(Student.school_id.in_(school_ids)).group_by(Student.school_id).all())
        if school_ids else {}
    )
    class_counts = (
        dict(db.query(Classroom.school_id, func.count()).filter(Classroom.school_id.in_(school_ids)).group_by(Classroom.school_id).all())
        if school_ids else {}
    )
    items = []
    for sc in rows:
        d = to_dict(sc)
        d["student_count"] = student_counts.get(sc.id, 0)
        d["class_count"] = class_counts.get(sc.id, 0)
        items.append(d)
    return {"items": items, "total": len(items)}


def create_school(db: Session, user: User, payload: dict) -> dict:
    """创建学校（仅平台超管），可选同步创建首位学校管理员。"""
    if not is_platform_admin(user):
        raise HTTPException(status_code=403, detail="只有平台超管可以创建学校")
    ensure_school_code_unique(db, payload.get("code"))
    name = (payload.get("name") or "").strip()
    code = (payload.get("code") or "").strip()
    if not name or not code:
        raise HTTPException(status_code=400, detail="学校名称和代码不能为空")
    s = School(
        name=name, code=code, address=payload.get("address"),
        phone=payload.get("phone"), created_by=user.id,
    )
    db.add(s)
    db.flush()

    # 同步创建该校首位学校管理员（可选）
    admin_username = (payload.get("admin_username") or "").strip()
    if admin_username:
        if db.query(User).filter(
            User.school_id == s.id, User.username == admin_username
        ).first():
            raise HTTPException(status_code=400, detail="该校已存在同名管理员账号")
        pwd = payload.get("admin_password") or "School@123"
        db.add(User(
            username=admin_username,
            password_hash=hash_password(pwd),
            name=(payload.get("admin_name") or "").strip() or admin_username,
            role="school_admin",
            school_id=s.id,
            must_change_password=validate_password_strength(pwd) is not None,
        ))

    audit(db, user, "create_school", target=f"新增学校-{name}")
    db.commit()
    db.refresh(s)
    data = to_dict(s)
    data["admin_username"] = admin_username or None
    return data


def update_school(db: Session, user: User, school_id: int, payload: dict) -> dict:
    """更新学校信息（仅平台超管）。"""
    if not is_platform_admin(user):
        raise HTTPException(status_code=403, detail="只有平台超管可以修改学校")
    s = db.get(School, school_id)
    if not s:
        raise HTTPException(status_code=404, detail="学校不存在")
    new_code = payload.get("code")
    if new_code and new_code != s.code:
        ensure_school_code_unique(db, new_code)
    for f in ("name", "code", "address", "phone", "status"):
        if f in payload and payload[f] is not None:
            setattr(s, f, payload[f])
    audit(db, user, "update_school", target=f"学校#{school_id}")
    db.commit()
    return to_dict(s)


def delete_school(db: Session, user: User, school_id: int) -> dict:
    """删除学校（仅平台超管，存在班级时拒绝）。"""
    if not is_platform_admin(user):
        raise HTTPException(status_code=403, detail="只有平台超管可以删除学校")
    s = db.get(School, school_id)
    if not s:
        raise HTTPException(status_code=404, detail="记录不存在")
    # 有班级或学生的学校禁止删除，避免产生孤儿数据
    if db.query(Classroom).filter(Classroom.school_id == s.id).count():
        raise HTTPException(status_code=400, detail="该校仍有班级数据，请先停用而非删除")
    db.delete(s)
    audit(db, user, "delete_school", target=f"学校#{school_id}")
    db.commit()
    return {"ok": True}


def ensure_school_code_unique(db: Session, code: str | None, exclude_id: int | None = None) -> None:
    """校验学校代码唯一（空值跳过）。"""
    code = (code or "").strip()
    if not code:
        return
    q = db.query(School).filter(School.code == code)
    if exclude_id:
        q = q.filter(School.id != exclude_id)
    if q.first():
        raise HTTPException(status_code=400, detail="学校代码已存在")


def set_school_status(db: Session, user: User, school_id: int, payload: dict) -> dict:
    """启用 / 停用学校（仅平台超管）。停用后该校全部账号不可登录。"""
    if not is_platform_admin(user):
        raise HTTPException(status_code=403, detail="只有平台超管可以启停学校")
    status = payload.get("status")
    if status not in ("active", "disabled"):
        raise HTTPException(status_code=400, detail="状态值应为 active 或 disabled")
    s = db.get(School, school_id)
    if not s:
        raise HTTPException(status_code=404, detail="学校不存在")
    s.status = status
    audit(db, user, "set_school_status", target=f"学校#{school_id}-{status}")
    db.commit()
    return to_dict(s)


# ---------------- 班级 ----------------
def list_classrooms(db: Session, user: User, graduated: str = "") -> dict:
    """班级列表：管理员看所有班级，教师只看自己负责的班级。"""
    is_admin = is_any_admin(user)
    query = filter_classrooms_by_teacher(db, user.id, is_admin)
    # 毕业筛选："" 全部；"false" 未毕业；"true" 已毕业
    if graduated == "false":
        query = query.filter(Classroom.is_graduated.is_(False))
    elif graduated == "true":
        query = query.filter(Classroom.is_graduated.is_(True))
    rows = query.all()
    # 一次聚合查询各班级在籍学生数，避免逐班 count 的 N+1
    class_ids = [c.id for c in rows]
    student_counts = (
        dict(
            db.query(Student.class_id, func.count())
            .filter(Student.class_id.in_(class_ids), Student.is_dropped_out.is_(False))
            .group_by(Student.class_id)
            .all()
        )
        if class_ids else {}
    )
    # 一次查询所有班主任，避免逐班 db.get(User) 的 N+1
    teacher_ids = {c.teacher_id for c in rows if c.teacher_id}
    teacher_map = {t.id: t.name for t in db.query(User).filter(User.id.in_(teacher_ids)).all()} if teacher_ids else {}
    items = []
    for c in rows:
        d = to_dict(c)
        d["teacher_name"] = teacher_map.get(c.teacher_id)
        # 在籍学生数（不含退学）
        d["student_count"] = student_counts.get(c.id, 0)
        items.append(d)
    return {"items": items, "total": len(items)}


def _sync_head_teacher_class(db: Session, classroom, new_teacher_id):
    """班主任身份同步：以 classrooms.teacher_id 为唯一权威源，回写 users.class_id。

    班级管理设置班主任时只写 classrooms.teacher_id，而账号管理的「班级」列读的是
    users.class_id，两处不联动就会出现「班级为空、但班级身份是某班班主任」的矛盾。
    这里在班主任变更（设置 / 更换 / 取消）时同步维护 users.class_id：

    - 新班主任：class_id 指向本班（若其仍担任其它班班主任则保留原值，避免覆盖）
    - 原班主任：卸任后若 class_id 仍指向本班则清空，避免残留
    - new_teacher_id 为 None 表示取消班主任
    """
    old_teacher_id = classroom.teacher_id
    if old_teacher_id and old_teacher_id != new_teacher_id:
        old = db.get(User, old_teacher_id)
        if old is not None and old.class_id == classroom.id:
            old.class_id = None
    if new_teacher_id:
        t = db.get(User, new_teacher_id)
        if t is not None:
            other_head = (
                db.query(Classroom)
                .filter(Classroom.teacher_id == new_teacher_id, Classroom.id != classroom.id)
                .first()
            )
            if other_head is None:
                t.class_id = classroom.id
    classroom.teacher_id = new_teacher_id


def create_classroom(db: Session, user: User, payload: dict) -> dict:
    """创建班级（仅管理员）。"""
    if not is_any_admin(user):
        raise HTTPException(status_code=403, detail="只有管理员可以创建班级")
    name = (payload.get("name") or "").strip()
    code = (payload.get("code") or "").strip()
    if not name or not code:
        raise HTTPException(status_code=400, detail="班级名称和代码不能为空")
    if db.query(Classroom).filter(Classroom.code == code).first():
        raise HTTPException(status_code=400, detail="班级代码已存在")
    # 归属学校：平台超管必须显式指定；学校管理员默认取本校
    # 🔴 必须先校验「请求体里的 school_id 属于本校」：`before_flush` 只在未赋值时回填，
    # 显式传入他校 id 不会被纠正 ⇒ 学校管理员能把班级建到他校去。
    ensure_same_school(user, payload.get("school_id"))
    school_id = payload.get("school_id") or user.school_id
    if not school_id:
        raise HTTPException(status_code=400, detail="请指定所属学校")
    c = Classroom(
        school_id=school_id,
        name=name,
        code=code,
        major=payload.get("major"),
        grade=payload.get("grade"),
        teacher_id=payload.get("teacher_id"),
        is_graduated=bool(payload.get("is_graduated", False)),
    )
    db.add(c)
    db.flush()  # 先取到 c.id，才能把班主任身份同步到 users.class_id
    _sync_head_teacher_class(db, c, c.teacher_id)
    audit(db, user, "create_classroom", target="新增班级")
    db.commit()
    db.refresh(c)
    return to_dict(c)


def update_classroom(db: Session, user: User, class_id: int, payload: dict) -> dict:
    """更新班级信息。"""
    c = db.get(Classroom, class_id)
    if not c:
        raise HTTPException(status_code=404, detail="班级不存在")
    # 教师只能修改自己可操作的班级（班主任或科任）
    if not is_any_admin(user) and not is_teacher_class_owner(db, user.id, class_id):
        raise HTTPException(status_code=403, detail="无权修改该班级")
    # 教师不能修改班级对应的教师。判定用**值比较**，不能用「请求体里有没有这个键」：
    # 前端若改成整行提交（连同未改动的 teacher_id 一起回传，同 StudentFormDialog.vue），
    # 键存在性会把「没换班主任」误当成「换班主任」而报 403 —— 即 update_student 线上
    # 故障的同形写法。值比较同时堵住「传 null 清空班主任」（None != 当前值 → 403）。
    if not is_any_admin(user) and "teacher_id" in payload and payload["teacher_id"] != c.teacher_id:
        raise HTTPException(status_code=403, detail="教师无权修改班级对应的教师")
    # 管理员修改 teacher_id 时校验目标必须是教师角色
    if is_any_admin(user) and "teacher_id" in payload and payload["teacher_id"] is not None:
        t = db.get(User, payload["teacher_id"])
        if not t or t.role != "teacher":
            raise HTTPException(status_code=400, detail="所选教师不存在或不是教师角色")
    for f in ("name", "code", "major", "grade", "is_graduated"):
        if f in payload and payload[f] is not None:
            setattr(c, f, payload[f])
    # teacher_id 单独处理：原来的 `payload[f] is not None` 判断会静默忽略“清空班主任”，
    # 导致管理员在编辑框里删掉班主任后保存无效。这里显式允许 None 并在变更时同步 users.class_id。
    if "teacher_id" in payload:
        _sync_head_teacher_class(db, c, payload.get("teacher_id"))
    audit(db, user, "update_classroom", target=f"班级#{class_id}")
    db.commit()
    return to_dict(c)


def delete_classroom(db: Session, user: User, class_id: int) -> dict:
    """删除班级（仅管理员）。"""
    if not is_any_admin(user):
        raise HTTPException(status_code=403, detail="只有管理员可以删除班级")
    c = db.get(Classroom, class_id)
    if not c:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(c)
    audit(db, user, "delete_classroom", target=f"班级#{class_id}")
    db.commit()
    return {"ok": True}


# ---------------- 班级教师（班主任 + 科任） ----------------
def list_class_teachers(db: Session, user: User, class_id: int) -> dict:
    """查看班级的教师（班主任 + 科任老师）。一次批量查询教师，避免逐条 db.get 的 N+1。"""
    c = db.get(Classroom, class_id)
    if not c:
        raise HTTPException(status_code=404, detail="班级不存在")
    if not is_any_admin(user) and not is_teacher_class_owner(db, user.id, class_id):
        raise HTTPException(status_code=403, detail="无权查看该班级教师")
    cts = db.query(ClassTeacher).filter(ClassTeacher.class_id == class_id).all()
    teacher_ids = {ct.teacher_id for ct in cts}
    if c.teacher_id:
        teacher_ids.add(c.teacher_id)
    tmap = {t.id: t for t in db.query(User).filter(User.id.in_(teacher_ids)).all()} if teacher_ids else {}
    teachers = []
    if c.teacher_id:
        head = tmap.get(c.teacher_id)
        if head:
            teachers.append(
                {"teacher_id": head.id, "name": head.name, "username": head.username, "is_head": True}
            )
    for ct in cts:
        t = tmap.get(ct.teacher_id)
        if t:
            teachers.append(
                {"teacher_id": t.id, "name": t.name, "username": t.username, "is_head": False}
            )
    return {"items": teachers}


def add_class_teacher(db: Session, user: User, class_id: int, payload: dict) -> dict:
    """添加科任老师（仅管理员）。"""
    if not is_any_admin(user):
        raise HTTPException(status_code=403, detail="只有管理员可以配置科任老师")
    c = db.get(Classroom, class_id)
    if not c:
        raise HTTPException(status_code=404, detail="班级不存在")
    teacher_id = payload.get("teacher_id")
    t = db.get(User, teacher_id)
    if not t or t.role != "teacher":
        raise HTTPException(status_code=400, detail="所选教师不存在或不是教师角色")
    if c.teacher_id == teacher_id:
        raise HTTPException(status_code=400, detail="该教师已是班主任")
    if db.query(ClassTeacher).filter(
        ClassTeacher.class_id == class_id, ClassTeacher.teacher_id == teacher_id
    ).first():
        raise HTTPException(status_code=400, detail="该教师已是科任老师")
    db.add(ClassTeacher(class_id=class_id, teacher_id=teacher_id))
    audit(db, user, "add_class_teacher", target=f"班级#{class_id}-新增科任老师#{teacher_id}", class_id=class_id)
    db.commit()
    return {"ok": True}


def remove_class_teacher(db: Session, user: User, class_id: int, teacher_id: int) -> dict:
    """移除科任老师（仅管理员）。"""
    if not is_any_admin(user):
        raise HTTPException(status_code=403, detail="只有管理员可以配置科任老师")
    ct = db.query(ClassTeacher).filter(
        ClassTeacher.class_id == class_id, ClassTeacher.teacher_id == teacher_id
    ).first()
    if not ct:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(ct)
    audit(db, user, "remove_class_teacher", target=f"班级#{class_id}-移除科任老师#{teacher_id}", class_id=class_id)
    db.commit()
    return {"ok": True}


# ---------------- 学生 ----------------
def _students_permission_select(db: Session, user: User, is_admin: bool):
    """教师数据权限 + 本校隔离的 `select(Student)` 基语句（等价于 filter_students_by_teacher）。

    改为 2.0 风格 `select()` 以配合 `app.pagination.paginate`（要求传入未加 offset/limit
    的 select）。语义与原 Query 完全一致。
    """
    teacher = db.get(User, user.id)
    school_id = teacher.school_id if teacher else None
    stmt = select(Student)
    if school_id is not None:
        stmt = stmt.where(Student.school_id == school_id)
    if not is_admin:
        class_ids = get_teacher_class_ids(db, user.id)
        stmt = stmt.where(Student.class_id.in_(class_ids)) if class_ids else stmt.where(False)
    return stmt


def list_students(
    db: Session,
    user: User,
    class_id: int | None = None,
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    dropped_out: str = "",
) -> dict:
    """学生列表（分页）。单次 SQL 取回当前页 + 总数（见 app.pagination.paginate）。"""
    page, page_size = normalize_page(page, page_size)
    # 管理员看所有学生，教师只看自己负责班级的学生
    is_admin = is_any_admin(user)
    stmt = _students_permission_select(db, user, is_admin)
    if class_id:
        if not is_admin and not is_teacher_class_owner(db, user.id, class_id):
            raise HTTPException(status_code=403, detail="无权查看该班级的学生")
        stmt = stmt.where(Student.class_id == class_id)
    if keyword:
        stmt = stmt.where(Student.name.contains(keyword) | Student.student_no.contains(keyword))
    # 退学筛选："" 全部；"false" 在籍（未退学）；"true" 已退学
    if dropped_out == "false":
        stmt = stmt.where(Student.is_dropped_out.is_(False))
    elif dropped_out == "true":
        stmt = stmt.where(Student.is_dropped_out.is_(True))
    rows, total = paginate(db, stmt.order_by(Student.id), page, page_size)
    return {"items": _students_out(db, rows), "total": total}


def create_student(db: Session, user: User, payload: StudentCreate) -> dict:
    """新增学生，并自动同步生成学生登录账号。"""
    name = payload.name.strip()
    student_no = payload.student_no.strip()
    class_id = payload.class_id
    if not name or not student_no:
        raise HTTPException(status_code=400, detail="姓名和学号不能为空")
    # 已毕业班级不可再添加学生
    if class_id:
        ensure_class_operable(db, class_id)
    # 教师只能在自己负责的班级添加学生（且必须指定班级）
    if not is_any_admin(user):
        if not class_id:
            raise HTTPException(status_code=403, detail="教师必须选择自己负责的班级")
        if not is_teacher_class_owner(db, user.id, class_id):
            raise HTTPException(status_code=403, detail="无权在该班级添加学生")
    if db.query(Student).filter(Student.student_no == student_no).first():
        raise HTTPException(status_code=400, detail="学号已存在")
    # 归属校验：显式指定的 school_id 必须是本校（平台超管不受限）
    ensure_same_school(user, payload.school_id)
    # 归属学校：优先显式指定，否则从班级推导，再否则取当前用户学校
    school_id = payload.school_id
    if not school_id and class_id:
        _cls = db.get(Classroom, class_id)
        school_id = _cls.school_id if _cls else None
    if not school_id:
        school_id = user.school_id
    s = Student(
        school_id=school_id,
        class_id=class_id,
        name=name,
        gender=payload.gender,
        birth_date=parse_date(payload.birth_date),
        student_no=student_no,
        major=payload.major,
        parent_name=payload.parent_name,
        parent_phone=payload.parent_phone,
        student_type=payload.student_type,
        is_dropped_out=payload.is_dropped_out,
    )
    db.add(s)
    db.flush()
    # 自动同步生成学生登录账号（班级 + 姓名，默认密码 123456）
    exists_user = get_student_account(db, class_id, name)
    if not exists_user:
        db.add(
            User(
                username=name,
                password_hash=hash_password("123456"),
                name=name,
                role="student",
                class_id=class_id,
            )
        )
    audit(db, user, "create_student", target=f"新增学生-{s.name} ({s.student_no})", student_id=s.id)
    db.commit()
    db.refresh(s)
    return _student_out(db, s)


def update_student(db: Session, user: User, student_id: int, payload: StudentUpdate) -> dict:
    """更新学生信息（含寄宿状态变更留痕）。"""
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(status_code=404, detail="学生不存在")
    # 教师只能修改自己负责班级的学生
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
        raise HTTPException(status_code=403, detail="无权修改该学生")
    # 退学/毕业限制：已毕业班级的学生不可修改；已退学学生仅允许改回在籍（重新激活）
    if s.class_id:
        cls = db.get(Classroom, s.class_id)
        if cls and cls.is_graduated:
            raise HTTPException(status_code=403, detail="该学生所在班级已毕业，无法修改")
    if s.is_dropped_out and payload.is_dropped_out is not False:
        raise HTTPException(status_code=403, detail="该学生已退学，无法修改（可将其改回在籍后操作）")
    data = payload.model_dump(exclude_unset=True)
    # 教师不得调整学生的班级归属。⚠️ 判据必须是「目标值 != 当前值」，不能只看「请求体里有没有
    # class_id」：前端编辑弹窗（StudentFormDialog.vue）刻意「整行原样提交」，未改动的 class_id
    # 也会带上；只判存在会把班主任改通宿/寄宿误判成转班（线上故障：403 教师无权修改学生班级）。
    if (
        not is_any_admin(user)
        and data.get("class_id") is not None
        and data["class_id"] != s.class_id
    ):
        raise HTTPException(status_code=403, detail="教师无权修改学生班级")
    old_type = s.student_type
    for f in (
        "name", "gender", "birth_date", "class_id", "major",
        "parent_name", "parent_phone", "student_type", "is_dropped_out",
    ):
        if f in data and data[f] is not None:
            setattr(s, f, parse_date(data[f]) if f == "birth_date" else data[f])
    # 记录寄宿/通学状态变更
    new_type = data.get("student_type")
    if new_type and new_type != old_type:
        db.add(StudentBoardHistory(
            student_id=s.id,
            old_type=old_type,
            new_type=new_type,
            changed_by=user.id,
        ))
    audit(db, user, "update_student", target=f"学生#{student_id}-{s.name}", student_id=student_id)
    db.commit()
    db.refresh(s)
    return _student_out(db, s)


def delete_student(db: Session, user: User, student_id: int) -> dict:
    """删除学生及其业务数据、登录账号与头像。"""
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(status_code=404, detail="学生不存在")
    # 教师只能删除自己负责班级的学生
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
        raise HTTPException(status_code=403, detail="无权删除该学生")
    # 退学/毕业限制
    ensure_student_operable(db, student_id)

    # 级联清理：删除该学生全部业务数据（成绩/考勤/表现/提交等），避免孤儿数据
    purge_student_data(db, student_id)

    # 同步删除对应的登录账号（users，通过班级+姓名定位），并清理其头像文件
    account = get_student_account(db, s.class_id, s.name)
    avatar_url = account.avatar if account else None

    db.delete(s)
    audit(db, user, "delete_student", target=f"{s.name} ({s.student_no})", student_id=student_id)
    db.commit()

    # 账号与头像：在档案删除成功后清理（账号删除失败不影响档案已删的结果）
    if account:
        # 删除账号前先级联清理引用该账号的业务数据，避免 MySQL 外键约束拒绝删除
        purge_user_data(db, account.id)
        db.delete(account)
        db.commit()
    delete_avatar_file(avatar_url)
    return {"ok": True}


def reset_student_password(db: Session, student_id: int, payload: dict, user: User) -> dict:
    """教师重置/修改学生密码（默认 123456）。"""
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(status_code=404, detail="学生不存在")
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
        raise HTTPException(status_code=403, detail="无权重置该学生密码")
    # 退学/毕业限制
    ensure_student_operable(db, student_id)
    new_pwd = payload.get("password") or "123456"
    # 弱密码标记首次登录强制改密
    must_change = validate_password_strength(new_pwd) is not None
    u = get_student_account(db, s.class_id, s.name)
    if not u:
        u = User(
            username=s.name,
            password_hash=hash_password(new_pwd),
            name=s.name,
            role="student",
            school_id=s.school_id,
            class_id=s.class_id,
            must_change_password=must_change,
        )
        db.add(u)
    else:
        u.password_hash = hash_password(new_pwd)
        u.must_change_password = must_change
    audit(db, user, "reset_student_password", target=f"{s.name} ({s.student_no})", student_id=student_id)
    db.commit()
    return {"ok": True}


def upload_student_avatar(db: Session, user: User, student_id: int, file) -> dict:
    """教师为学生上传头像。"""
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(status_code=404, detail="学生不存在")
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
        raise HTTPException(status_code=403, detail="无权为该学生上传头像")
    # 退学/毕业限制
    ensure_student_operable(db, student_id)

    original = file.filename or "avatar"
    ext = os.path.splitext(original)[1].lower()
    if ext not in _AVATAR_ALLOWED:
        raise HTTPException(status_code=400, detail=f"仅支持图片格式：{'、'.join(sorted(_AVATAR_ALLOWED))}")

    student_user = get_student_account(db, s.class_id, s.name)
    if not student_user:
        raise HTTPException(status_code=404, detail="学生账号不存在，请先创建学生档案")

    name = f"avatar_{student_user.id}_{uuid.uuid4().hex[:8]}{ext}"
    os.makedirs(_AVATAR_DIR, exist_ok=True)
    dest = os.path.join(_AVATAR_DIR, name)

    size = 0
    chunk_size = 1024 * 1024
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = file.file.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > _AVATAR_MAX_SIZE:
                    f.close()
                    os.remove(dest)
                    raise HTTPException(status_code=413, detail=f"头像文件不能超过 {_AVATAR_MAX_SIZE // (1024*1024)}MB")
                f.write(chunk)
    except HTTPException:
        raise
    except Exception:
        if os.path.exists(dest):
            os.remove(dest)
        raise

    if student_user.avatar:
        old_name = student_user.avatar.rsplit("/", 1)[-1]
        old_full = os.path.join(_AVATAR_DIR, old_name)
        if os.path.exists(old_full):
            os.remove(old_full)

    student_user.avatar = f"/uploads/avatars/{name}"
    audit(db, user, "upload_student_avatar", target=f"{s.name} ({s.student_no})", student_id=student_id)
    db.commit()
    return {"avatar": student_user.avatar}


def board_type_stats(db: Session, user: User, class_id: int | None = None) -> dict:
    """通学生 / 寄宿生人数对比及明细名单（不含退学学生）。"""
    q = db.query(Student).filter(Student.is_dropped_out.is_(False))
    # 教师只能看自己负责班级
    if not is_any_admin(user):
        class_ids = get_teacher_class_ids(db, user.id)
        if class_ids:
            q = q.filter(Student.class_id.in_(class_ids))
        else:
            q = q.filter(False)
    if class_id:
        q = q.filter(Student.class_id == class_id)
    students = q.all()
    day = [s for s in students if s.student_type == "day"]
    boarding = [s for s in students if s.student_type == "boarding"]
    return {
        "day_count": len(day),
        "boarding_count": len(boarding),
        "day": _students_out(db, day),
        "boarding": _students_out(db, boarding),
    }


def _board_label(t):
    """住宿类型 -> 中文标签。"""
    if t == "day":
        return "通学生"
    if t == "boarding":
        return "寄宿生"
    return "初始"


def _fmt_dt(dt):
    """datetime -> 展示用字符串，None 返回 None。"""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def get_board_history(db: Session, user: User, student_id: int) -> dict:
    """获取学生寄宿/通学状态：当前状态、各时间段（含起始/结束时间）与变更日志。"""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    changes = (
        db.query(StudentBoardHistory)
        .filter(StudentBoardHistory.student_id == student_id)
        .order_by(StudentBoardHistory.created_at.asc())
        .all()
    )

    # 一次批量查询变更人姓名，避免逐条 db.get(User) 的 N+1
    changer_map = batch_user_map(db, [r.changed_by for r in changes if r.changed_by])
    items = []
    for r in reversed(changes):
        d = to_dict(r)
        d["old_label"] = _board_label(r.old_type)
        d["new_label"] = _board_label(r.new_type)
        d["changed_at"] = _fmt_dt(r.created_at)
        if r.changed_by:
            u = changer_map.get(r.changed_by)
            d["changed_by_name"] = u["name"] if u else ""
        items.append(d)

    base_start = _fmt_dt(student.created_at) or "建档"
    periods = []
    if not changes:
        periods.append({
            "type": student.student_type,
            "label": _board_label(student.student_type),
            "start": base_start,
            "end": None,
        })
    else:
        periods.append({
            "type": changes[0].old_type,
            "label": _board_label(changes[0].old_type),
            "start": base_start,
            "end": _fmt_dt(changes[0].created_at),
        })
        for i, r in enumerate(changes):
            end = _fmt_dt(changes[i + 1].created_at) if i + 1 < len(changes) else None
            periods.append({
                "type": r.new_type,
                "label": _board_label(r.new_type),
                "start": _fmt_dt(r.created_at),
                "end": end,
            })

    current = {
        "type": student.student_type,
        "label": _board_label(student.student_type),
        "since": _fmt_dt(changes[-1].created_at) if changes else base_start,
    }

    return {"current": current, "periods": periods, "items": items}


def export_students(db: Session, user: User, class_id: int | None = None, dropped_out: str = "") -> StreamingResponse:
    """导出学生花名册为 Excel。"""
    q = db.query(Student)
    # 教师只能导出自己负责班级的学生
    if not is_any_admin(user):
        class_ids = get_teacher_class_ids(db, user.id)
        if class_ids:
            q = q.filter(Student.class_id.in_(class_ids))
        else:
            q = q.filter(False)
    if class_id:
        q = q.filter(Student.class_id == class_id)
    # 默认导出在籍学生；dropped_out="true" 时导出已退学；"all" 导出全部
    if dropped_out == "true":
        q = q.filter(Student.is_dropped_out.is_(True))
    elif dropped_out == "all":
        pass
    else:
        q = q.filter(Student.is_dropped_out.is_(False))
    rows = q.order_by(Student.id).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "学生花名册"
    headers = ["学号", "姓名", "性别", "出生日期", "专业", "家长姓名", "家长电话", "类型", "是否退学"]
    ws.append(headers)
    for s in rows:
        ws.append(
            [
                s.student_no,
                s.name,
                s.gender,
                s.birth_date,
                s.major,
                s.parent_name,
                s.parent_phone,
                "通学生" if s.student_type == "day" else "寄宿生",
                "是" if s.is_dropped_out else "否",
            ]
        )
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=students.xlsx"},
    )
