"""班级权限检查模块"""
from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Classroom, ClassTeacher, School, Student, User


# ---------------- 角色与租户辅助 ----------------

def is_platform_admin(user) -> bool:
    """平台超管（跨学校）。"""
    return user.role == "super_admin"


def is_any_admin(user) -> bool:
    """平台超管或学校管理员。"""
    return user.role in ("super_admin", "school_admin")


def ensure_same_school(user, target_school_id: int | None) -> None:
    """校验目标资源属于当前用户学校；平台超管不受限，否则越权抛 403。"""
    if is_platform_admin(user):
        return
    if target_school_id is not None and target_school_id != user.school_id:
        raise HTTPException(status_code=403, detail="无权访问其他学校的数据")


def resolve_school_id_or_400(db: Session, user, requested_school_id: int | None) -> int | None:
    """解析「无父资源的学校级实体」归属 school_id（工作日志 / 计划 / 资源 / 试卷统一口径）。

    平台超管必须显式指定，否则 400；其他角色取 user.school_id 并忽略入参（防跨校写入）。
    """
    if is_platform_admin(user):
        if requested_school_id is None:
            raise HTTPException(status_code=400, detail="请选择学校")
        school = db.get(School, requested_school_id)
        if school is None:
            raise HTTPException(status_code=400, detail="学校不存在")
        return school.id
    return user.school_id


def _raise_if_student_inoperable(db: Session, student: Student) -> None:
    """退学/毕业封禁校验（内部共用）：命中即抛 403，文案与 ensure_student_operable 一致。"""
    if student.is_dropped_out:
        raise HTTPException(status_code=403, detail="该学生已退学，无法进行操作")
    if student.class_id:
        cls = db.get(Classroom, student.class_id)
        if cls and cls.is_graduated:
            raise HTTPException(status_code=403, detail="该学生所在班级已毕业，无法进行操作")


def ensure_student_operable(db: Session, student_id: int) -> Student:
    """校验学生是否可被教师/管理员操作。

    规则：
    - 学生不存在 -> 404
    - 学生已退学 -> 403（不可再对该生进行各项操作）
    - 学生所在班级已毕业 -> 403（不可再对该班所有学生进行各项操作）

    返回对应的 Student 实例，供调用方复用。
    """
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    _raise_if_student_inoperable(db, student)
    return student


def ensure_student_visible(
    db: Session,
    user: User,
    student_id: int,
    *,
    detail_403: str = "无权操作该学生的记录",
    check_operable: bool = True,
    operable_first: bool = True,
) -> Student:
    """学生域权限样板收口：校验学生存在、封禁状态与「教师是否带班」，返回 Student。

    统一语义（与既有各调用点逐字一致）：
    - 学生不存在 -> 404 "学生不存在"
    - ``check_operable=True`` 时叠加退学/毕业封禁校验（文案同 ``ensure_student_operable``）
    - 非管理员且教师不带班 -> 403 ``detail_403``（管理员放行）

    ``operable_first`` 控制封禁校验与带班校验**同时命中**时先抛哪个：
    workbench 增删改及 classlog 先 ``ensure_student_operable`` 再查带班（True，默认）；
    students_service 的删除/改密/头像则先查带班再查封禁（False）。
    收口要求触发顺序逐字保持，故以关键字参数承接这两种既有顺序。
    """
    if check_operable and operable_first:
        student = ensure_student_operable(db, student_id)
    else:
        student = db.get(Student, student_id)
        if not student:
            raise HTTPException(status_code=404, detail="学生不存在")
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
        raise HTTPException(status_code=403, detail=detail_403)
    if check_operable and not operable_first:
        _raise_if_student_inoperable(db, student)
    return student


def ensure_class_operable(db: Session, class_id: int) -> Classroom:
    """校验班级是否可被教师/管理员操作（未毕业）。

    班级已毕业 -> 403；班级不存在 -> 404。返回 Classroom 实例。
    """
    cls = db.get(Classroom, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")
    if cls.is_graduated:
        raise HTTPException(status_code=403, detail="该班级已毕业，无法进行操作")
    return cls


def get_teacher_class_ids(db: Session, teacher_id: int) -> List[int]:
    """获取教师可操作的班级ID列表（班主任班级 + 科任班级），限定本校。"""
    teacher = db.get(User, teacher_id)
    school_id = teacher.school_id if teacher else None
    q = db.query(Classroom)
    if school_id is not None:
        q = q.filter(Classroom.school_id == school_id)
    own_ids = {c.id for c in q.filter(Classroom.teacher_id == teacher_id).all()}
    own_ids.update(
        ct.class_id
        for ct in db.query(ClassTeacher).filter(ClassTeacher.teacher_id == teacher_id).all()
    )
    return sorted(own_ids)


def get_head_class_ids(db: Session, teacher_id: int) -> List[int]:
    """获取教师担任**班主任**的班级 ID 列表（不含科任班级）。

    与 `get_teacher_class_ids` 的区别：后者是「班主任班级 ∪ 科任班级」的并集，回答的是
    「我能否操作这个班」；本函数只回答「我是不是这个班的班主任」，用于
    `/admin/audit-logs` 的可见范围（刻意只给班主任）与前端菜单的可见性判断。
    """
    rows = db.query(Classroom).filter(Classroom.teacher_id == teacher_id).all()
    return sorted(c.id for c in rows)


def get_student_ids_in_class(db: Session, class_id: int) -> List[int]:
    """获取某班级的学生ID列表"""
    return [s.id for s in db.query(Student).filter(Student.class_id == class_id).all()]


def apply_teacher_student_filter(db: Session, user: User, q, model):
    """教师数据权限过滤：仅保留其负责班级学生的记录。

    返回 (query, denied)。管理员不限制（denied=False）；教师无班级时
    denied=True（调用方应返回空列表）；有班级则按 student_id 过滤。

    该模式在成绩/请假/沟通等列表接口大量重复，统一收口避免遗漏与不一致。
    """
    if is_any_admin(user):
        return q, False
    class_ids = get_teacher_class_ids(db, user.id)
    if not class_ids:
        return q.filter(False), True
    student_ids = [
        s.id for s in db.query(Student).filter(Student.class_id.in_(class_ids)).all()
    ]
    return q.filter(model.student_id.in_(student_ids)), False


def apply_student_class_filter(db: Session, user: User, q, class_id: int | None, model=None):
    """在班级筛选上叠加权限控制。

    返回 (query, 是否被拒绝)。teacher 访问非自己班级时返回 (q, True) 应直接返回空。

    注意：调用方必须传入 model 参数（SQLAlchemy 模型类，如 Score），
    因为函数内部需要用 model.student_id 做过滤。
    """
    if model is None:
        raise ValueError("apply_student_class_filter 需要传入 model 参数")
    if not is_any_admin(user):
        if class_id and not is_teacher_class_owner(db, user.id, class_id):
            return q, True
        class_ids = get_teacher_class_ids(db, user.id)
        if class_ids:
            student_ids = [s.id for s in db.query(Student).filter(Student.class_id.in_(class_ids)).all()]
            q = q.filter(model.student_id.in_(student_ids))
        else:
            return q.filter(False), False
    if class_id:
        student_ids = get_student_ids_in_class(db, class_id)
        q = q.filter(model.student_id.in_(student_ids))
    return q, False


def is_teacher_class_owner(db: Session, teacher_id: int, class_id: int) -> bool:
    """检查教师是否可操作某班级（班主任或科任老师）。"""
    if (
        db.query(Classroom)
        .filter(Classroom.id == class_id, Classroom.teacher_id == teacher_id)
        .first()
    ):
        return True
    return (
        db.query(ClassTeacher)
        .filter(ClassTeacher.class_id == class_id, ClassTeacher.teacher_id == teacher_id)
        .first()
        is not None
    )


def is_student_in_teacher_classes(db: Session, teacher_id: int, student_id: int) -> bool:
    """检查学生是否在教师负责的班级中"""
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student or not student.class_id:
        return False
    return is_teacher_class_owner(db, teacher_id, student.class_id)


def filter_classrooms_by_teacher(db: Session, teacher_id: int, is_admin: bool):
    """根据教师身份过滤班级查询（班主任 + 科任），限定本校。"""
    teacher = db.get(User, teacher_id)
    school_id = teacher.school_id if teacher else None
    query = db.query(Classroom)
    if school_id is not None:
        query = query.filter(Classroom.school_id == school_id)
    if not is_admin:
        class_ids = get_teacher_class_ids(db, teacher_id)
        query = query.filter(Classroom.id.in_(class_ids)) if class_ids else query.filter(False)
    return query.order_by(Classroom.id)


def filter_students_by_teacher(db: Session, teacher_id: int, is_admin: bool):
    """根据教师身份过滤学生查询，限定本校。"""
    teacher = db.get(User, teacher_id)
    school_id = teacher.school_id if teacher else None
    query = db.query(Student)
    if school_id is not None:
        query = query.filter(Student.school_id == school_id)
    if not is_admin:
        class_ids = get_teacher_class_ids(db, teacher_id)
        if class_ids:
            query = query.filter(Student.class_id.in_(class_ids))
        else:
            query = query.filter(False)
    return query.order_by(Student.id)


def get_student_account(db: Session, class_id: int, name: str) -> User | None:
    """通过「班级 + 姓名」定位学生登录账号（role=student），不存在返回 None。

    ⚠️ 本函数**保持软匹配不变**：它的入参就是 ``(class_id, name)``，语义即
    「给我这个班里叫这个名字的账号」，不存在可用于改写的 ``student_id`` ——
    调用方手里只有班级与姓名，没有档案 id。改为硬外键需要一个额外的「档案 → 账号」
    入口函数（见 ``get_student_avatar`` 的硬外键分支），不在本函数职责内。
    因此这里保留原样，仅延续既有 ``.first()`` 语义（该项目账号唯一性由
    ``users.username_scope`` 复合唯一约束在库层保证，见 models/user.py）。
    """
    if not class_id or not name:
        return None
    return (
        db.query(User)
        .filter(User.role == "student", User.class_id == class_id, User.name == name)
        .first()
    )


def get_student_by_account(db: Session, user: User) -> Student | None:
    """通过学生登录账号（User）定位其学生档案（Student），不存在返回 None。

    优先走 **硬外键** ``user.student_id``：直接、唯一、不受改名/同名影响。
    仅当 ``student_id`` 为空（非学生角色、档案未建、或迁移期歧义未回填）时，
    才回落到旧的 ``(class_id, name)`` 软匹配，保证未回填的历史数据不立即坏掉。

    🔴 租户校验（defense-in-depth）：这里**显式比对** ``school_id``，防范
    ``db.get`` 的 **identity-map 短路**。

    精确机制（实测，勿误读）：``db.get(Model, pk)`` **本身并不普遍绕过**租户过滤 ——
    在 **fresh session** 下，它会正常触发 ``do_orm_execute``，``with_loader_criteria``
    的 ``school_id`` 条件被注入，跨租户 PK 返回 None（探针实测：SQL 1 次、返回 None）。
    真正会绕过的是**同一 Session 内该对象已在 identity map 中**：若它此前被某条
    ``execution_options(skip_tenant_filter=True)`` 的查询（全项目 16 处，2026-10-01 实测：
    platform_settings / admin_service / ai_grading / auth_service / homework_service）
    或平台超管分支加载过，
    则 ``db.get`` 直接返回缓存对象、**零 SQL、零事件** ⇒ 过滤无从生效。
    （注：``skip_tenant_filter`` 见 ``app/tenant.py::_apply_tenant_filter``。）

    因此显式 ``school_id`` 比对是对上述短路的兜底：即便拿到跨租户缓存对象，
    也会被这里拦下返回 None。平台超管（``school_id is None``）跨租户属预期，放行。
    """
    if not user:
        return None

    # 硬外键优先
    if getattr(user, "student_id", None) is not None:
        stu = db.get(Student, user.student_id)
        if stu is not None:
            # 同租户校验：仅当双方 school_id 均已知且不一致时判定越界。
            if (
                user.school_id is not None
                and stu.school_id is not None
                and stu.school_id != user.school_id
            ):
                return None
            return stu

    # 回落：软匹配（历史账号 student_id 尚未回填）
    if user.class_id is None:
        return None
    return (
        db.query(Student)
        .filter(Student.class_id == user.class_id, Student.name == user.name)
        .first()
    )


def get_student_avatar(db: Session, student) -> str | None:
    """通过学生档案定位其登录账号头像（users.avatar），不存在返回 None。

    头像统一存于 users.avatar，students 表不再冗余存储。

    优先走硬外键：用 ``student.id`` 反查 ``users.student_id``（有索引
    ``ix_users_student_id``）；查不到再回落到 ``(class_id, name)`` 软匹配。
    该 queries 走 ORM ``query()``，因此自然受租户过滤管辖，无需额外显式校验。
    """
    if not student:
        return None
    u = (
        db.query(User)
        .filter(User.role == "student", User.student_id == student.id)
        .first()
    )
    if u is None:
        # 回落：软匹配
        u = get_student_account(db, student.class_id, student.name)
    return u.avatar if u else None
