"""班级权限检查模块"""
import logging
from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Classroom, ClassTeacher, School, Student, User

logger = logging.getLogger("teachhub.permissions")


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

    ⚠️ **仅用于「还没有 Student 档案对象」的入口**（如建档前查重、导入查重、注册查重）。
    凡是调用方手里已有 ``Student`` 的地方，一律改用 ``get_account_of_student`` ——
    软匹配会在改名/转班后命中错人（2026-10-25 修 RBT-35：删 B 的账号删掉了 A 的、
    重置 B 的密码改掉了 A 的）。

    🔴 本函数**只回答「这把软钥匙当前指向哪个账号」，不回答「这个账号是不是他的」**
    （RBT-65：同班同名时它会返回**同学**的账号）。因此它的返回值**绝不能**用于
    删除账号 / 改密码 / 改身份这类写操作，只能用于「查重时要不要提示已存在」。
    要判断归属，用 ``get_account_of_student``（唯一可判定的兜底）或
    ``find_account_conflict``（把冲突讲清楚）。

    本函数本身仍保留软匹配语义：入参只有班级与姓名，没有可用于改写的 ``student_id``。
    账号唯一性由 ``users.username_scope`` 复合唯一约束在库层保证（见 models/user.py）。
    """
    if not class_id or not name:
        return None
    return (
        db.query(User)
        .filter(User.role == "student", User.class_id == class_id, User.name == name)
        .first()
    )


def _same_name_student_count(db: Session, class_id: int | None, name: str | None) -> int:
    """同班同名**档案**数（判定「班级 + 姓名」这把软钥匙是否还有唯一候选）。"""
    return (
        db.query(Student)
        .filter(Student.class_id == class_id, Student.name == name)
        .count()
    )


def _legacy_account(db: Session, student: Student) -> User | None:
    """软匹配兜底：**只在归属唯一可判定时**返回账号，否则返回 None 并记 warning。

    调用方：``get_account_of_student``（档案 → 账号，命中后回填硬外键）、
    ``get_student_avatar``（只读，不回填）。

    判据（缺一不可，RBT-65）：

    1. 命中账号的 ``student_id`` 必须为空 —— 非空且指向别的档案，说明这把软钥匙
       指向的是**同班同名同学**，返回它等于把「删错账号 / 改错密码」重新引回来；
    2. 同班同名档案必须**恰好一份** —— 有多份时「这个 ``student_id`` 为空的账号是
       谁的」根本无从判定，回填等于随机认领，宁可不认（返回 None，让调用方给出
       「同班同名无法自动建号」的明确提示）。
    """
    if not student or not student.class_id or not student.name:
        return None
    u = get_student_account(db, student.class_id, student.name)
    if u is None:
        return None
    if u.student_id is not None:
        if u.student_id == student.id:
            # 硬外键已命中（正常不会走到这里），防御性保留
            return u
        logger.warning(
            "软匹配命中同班同名账号#%s（属于档案#%s），与当前档案#%s 归属不同，已拒绝采用",
            u.id, u.student_id, student.id,
        )
        return None
    same_name = _same_name_student_count(db, student.class_id, student.name)
    if same_name > 1:
        logger.warning(
            "同班同名档案共 %s 份（班级#%s 姓名「%s」），账号#%s 的 student_id 为空、"
            "归属无法唯一判定，已拒绝采用（可用 find_account_conflict 向调用方说明原因）",
            same_name, student.class_id, student.name, u.id,
        )
        return None
    return u


def find_account_conflict(
    db: Session,
    class_id: int | None,
    name: str | None,
    *,
    student_id: int | None = None,
) -> User | None:
    """返回**挡住**为 ``(class_id, name)`` 建号的账号，没有则 None。

    用途单一：把「为什么这个学生建不了登录账号」讲成人话（409 文案 / 导入行错误），
    避免「静默不建号但接口 200」（RBT-66）。**绝不能**拿返回值去做删除 / 改密 / 改身份
    —— 它正是 ``get_account_of_student`` 刻意拒绝返回的那个账号。

    Args:
        class_id / name: 目标学生档案的班级与姓名。
        student_id: **该学生自己的档案 id**；建号前档案还没入库时传 None（默认）。
            ``None`` 与「已入库」的判据差异只出现在「账号 ``student_id`` 为空」这一支：
            档案已入库时它可能是**这名学生本人**的历史账号（同班同名仅此一份即可认领）；
            档案尚未入库时则要看同班是否已有同名档案 —— 有（说明账号是同学的）判冲突，
            没有（说明是已删学生遗留的**孤儿账号**）放行，由 ``get_account_of_student``
            在建档后认领回填，而不是让教师先去清理孤儿。

    与 ``_legacy_account`` 严格互补：``get_account_of_student`` 返回 None 时，本函数
    要么给出被占用的账号，要么返回 None（说明确实没有账号，可以安全建号）。
    """
    if not class_id or not name:
        return None
    u = get_student_account(db, class_id, name)
    if u is None:
        return None
    if u.student_id is not None:
        return None if u.student_id == student_id else u
    # 账号 student_id 为空：档案未入库 ⇒ 看是否已有同名档案（无 ⇒ 孤儿账号，可认领）；
    # 档案已入库 ⇒ 同班同名唯一才可能是它的，否则归属无从判定，判冲突。
    same_name = _same_name_student_count(db, class_id, name)
    if student_id is None:
        return u if same_name > 0 else None
    return u if same_name > 1 else None


def get_account_of_student(db: Session, student: Student) -> User | None:
    """由**学生档案**定位其登录账号：硬外键优先，软匹配仅在归属唯一可判定时兜底。

    🔴 这是「档案 → 账号」的**唯一正路**（2026-10-25 修 RBT-35）。顺序：

    1. ``users.student_id == student.id`` —— 唯一、且不受改名/同班同名影响；
    2. 回落 ``(class_id, name)`` 软匹配，覆盖迁移期尚未回填 ``student_id`` 的历史行；
    3. 回落命中且该账号 ``student_id`` 为空、**且同班同名档案只有这一份**时顺手回填
       （调用方随后都会 commit），下一次定位就命中硬外键 —— 无需额外的数据修复脚本。

    🔴 **兜底必须校验归属（2026-11-03 修 RBT-65）**：旧实现在第 2 步只做
    ``(class_id, name)`` 查询就返回结果，于是同班同名的 B 会拿到 A 的账号，后果全部
    落在写操作上、且不可逆：``delete_student`` 会 ``purge_user_data`` 并删掉 A 的账号，
    ``reset_student_password`` 改掉 A 的密码，``update_student`` 把 A 的登录身份改掉。
    「同班同名 + 其中一人没有账号」不需要攻击者，正常业务就会产生（见 RBT-66）。

    因此第 2 步命中后一律经 ``_legacy_account`` 过滤：账号属于别人、或归属无从判定
    （同班同名多份档案 + ``student_id`` 为空）时**返回 None**，并记 warning。
    调用方拿到 None 时应把它当作「该生没有可用账号」——建号前先用
    ``find_account_conflict`` 区分「真没有」与「被同名账号占用」，后者给出明确错误。

    为什么不覆盖已有 ``student_id``：非空但指向别的档案属于**脏数据**，静默改写会把
    「账号挂错人」变成看不出发生过的事；保留它，交由 ``get_student_by_account`` 的
    租户校验与审计日志暴露。
    """
    if not student:
        return None
    u = (
        db.query(User)
        .filter(User.role == "student", User.student_id == student.id)
        .first()
    )
    if u is not None:
        return u
    u = _legacy_account(db, student)
    if u is not None:
        u.student_id = student.id
    return u


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
    ``execution_options(skip_tenant_filter=True)`` 的查询，或平台超管分支加载过，
    则 ``db.get`` 直接返回缓存对象、**零 SQL、零事件** ⇒ 过滤无从生效。

    这条推理的规模有多大，请**现算，别引用历史数字**（RDB-62：本注释原写「全项目 16 处」，
    2026-11-03 复核已在 25 处量级，多出来的正是 AI 链路）：

    ```
    grep -rn "skip_tenant_filter=True" app --include=*.py | wc -l
    # 2026-11-04 实测 27 行 = 代码调用 25 处 + 本文件 docstring 里的 2 处说明文字
    # 25 处分布：ai_grading 7 + homework_service 7 + platform_settings 5
    #           + auth_service 3 + ai_analysis 2 + admin_service 1
    ```

    （注：``skip_tenant_filter`` 见 ``app/tenant.py::_apply_tenant_filter``。）

    因此显式 ``school_id`` 比对是对上述短路的兜底：即便拿到跨租户缓存对象，
    也会被这里拦下返回 None。平台超管（``school_id is None``）跨租户属预期，放行。

    软匹配兜底同样要判歧义：``(class_id, name)`` 命中多份档案时返回 None（见下方注释），
    这是 RBT-65 的反方向 —— 猜错档案等于把**同学的数据**返回给当前学生。
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
    # 🔴 反方向也要判歧义（RBT-65 的另一半）：同班同名多份档案时 `.first()` 是随机认领，
    # 一旦认到别人档案，该生这个请求看到的就是**同学的作业/成绩/学伴记录**（越权读）。
    # 宁可查不到（调用方按无档案处理），也不猜。实测库中 `student_id` 为空的学生账号
    # 0 条（2026-11-04），该分支只服务于迁移期数据。
    same_name = _same_name_student_count(db, user.class_id, user.name)
    if same_name > 1:
        logger.warning(
            "账号#%s 的 student_id 为空且班级#%s 姓名「%s」有 %s 份档案，"
            "归属无从判定，已拒绝按软匹配返回（避免读到同学数据）",
            user.id, user.class_id, user.name, same_name,
        )
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
    ``ix_users_student_id``）；查不到再回落到 ``(class_id, name)`` 软匹配 —— 但必须
    与 ``get_account_of_student`` 同一套归属校验（``_legacy_account``），否则同班同名的
    B 会显示 A 的头像（RBT-65 的同类表现）。该 queries 走 ORM ``query()``，因此自然
    受租户过滤管辖，无需额外显式校验；**只读，不回填** ``student_id``。
    """
    if not student:
        return None
    u = (
        db.query(User)
        .filter(User.role == "student", User.student_id == student.id)
        .first()
    )
    if u is None:
        # 回落：软匹配（仅当归属唯一可判定，见 `_legacy_account`）
        u = _legacy_account(db, student)
    return u.avatar if u else None
