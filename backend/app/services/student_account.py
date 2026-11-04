"""学生登录账号的唯一建号入口（审计 SMP-24）。

本模块**只依赖** ``app.models.user.User`` 与 ``app.security``（不 import 任何 service
模块），因此可以被 ``students_service`` / ``workbench.imports_service`` /
``auth_service`` 任意方向引用而**不产生循环 import**。反向依赖（本模块 import 上面
那些 service）是禁止的。

改这一段前请先读 ``build_student_user`` 的 docstring：里面有 4 条 🔴 铁律，全部由
历史事故换来。
"""
from app.models.user import User
from app.security import hash_password, validate_password_strength

# 学生默认口令。印在启动日志里的演示口径与它一致；弱口令会由工厂自动置
# ``must_change_password``，因此「默认口令长期可用」不再是隐患（SMP-24）。
DEFAULT_STUDENT_PASSWORD = "123456"


def student_account_conflict_detail(name: str) -> str:
    """同班同名导致无法建号时的用户可读说明（409 文案 / 导入行错误共用同一口径）。

    为什么必须「明确失败」而不是「静默跳过」（RBT-66）：学生登录名就是姓名，唯一性由
    ``uq_user_scope_username`` = ``(username_scope, username)`` 在库层保证，学生的 scope
    是 ``stu:<school>:<class>`` —— 同班两名同名学生**在现行 schema 下无法各有账号**
    （``update_student`` 把学生转进有同名同学的班时也是 409，口径一致）。
    旧实现遇到这种情况只是「跳过建号」然后返回 200，教师以为账号已建好，
    直到该生登录失败才发现。

    纯字符串函数，不 import 任何东西 —— 保持本模块「只依赖 models + security」的边界。
    """
    return (
        f"同班已存在同名账号「{name}」，无法为该学生创建登录账号"
        "（学生登录名即姓名，同班内必须唯一）。"
        "请先处理该同名账号，或为该学生使用可区分的姓名后重试。"
    )


def build_student_user(
    *,
    name: str,
    school_id: int | None,
    class_id: int | None,
    student_id: int,
    password: str = DEFAULT_STUDENT_PASSWORD,
) -> User:
    """构造一个**尚未入库**的学生登录账号（``User`` 实例），学生建号的唯一入口。

    审计 SMP-24 的根因就是「学生建号有 6 份实现」：其中「教师新建学生」与「Excel
    导入学生」两条路径手写 ``User(...)`` 时**漏了 `must_change_password`**，于是默认
    口令 ``123456`` 可以被长期使用（登录后不触发强制改密）。新增建号路径时**必须**调用
    本函数，不要再手写 ``User(role="student", ...)``。

    Args:
        name: 学生姓名。学生账号的 ``username`` 就是姓名（唯一性作用域见
            ``User.compute_username_scope``：``stu:<school_id>:<class_id>``）。
        school_id: 🔴 **必须显式传**（见下）。
        class_id: 所属班级 id（学生账号的唯一性作用域之一，同时也是数据隔离口径）。
        student_id: 🔴 **必须回填**，档案 ↔ 账号的硬锚点。
        password: 初始口令，默认 ``DEFAULT_STUDENT_PASSWORD``。

    Returns:
        未加入 session 的 ``User`` 实例；由调用方 ``db.add(...)`` / ``db.flush()``。

    🔴 铁律一：``school_id`` **必须显式传**。
        ``User`` 的 ``before_flush`` 事件只在**租户上下文非 None** 时回填 ``school_id``；
        平台超管上下文是 None ⇒ 不回填 ⇒ 落 NULL。而 ``school_id IS NULL`` 的账号在
        ``tenant.py`` 里**既不过滤也不回填**，等于一个**跨校读写全平台**的账号
        （2026-09-26 已实证：超管建学生后 ``User.school_id=None`` 而
        ``Student.school_id=1``，见 docs/REVIEW-2026-09-25-code-audit.md P1-B）。

    🔴 铁律二：``student_id`` **必须回填**。
        它是「档案 ↔ 账号」唯一稳定锚点（RBT-35）。缺了它，此后一切定位只能靠
        「班级 + 姓名」软匹配 —— 学生改名 / 转班就会串人（改错密码、删错档案；
        档案 → 账号方向另见 ``permissions.get_account_of_student``）。

    🔴 铁律三：``must_change_password`` 由密码强度**自动推导**，调用方**不得自选**。
        这正是「教师新建学生」与「Excel 导入学生」两条路径漏置该标记、导致默认口令
        ``123456`` 可长期使用的根因（审计 SMP-24）。弱口令一律强制首登改密；反过来
        调用方也不能硬编码 False 来「跳过改密」，那等于把这条路又开回去。

    🔴 铁律四：``username`` / ``name`` 都取 ``name``（学生以姓名为登录名），不要在此
        追加学号后缀或去重逻辑 —— 唯一性由 ``uq_user_scope_username`` 在 DB 层兜底，
        上层（``students_service`` 等）负责给出 409 之类的友好错误。
    """
    return User(
        username=name,
        password_hash=hash_password(password),
        name=name,
        role="student",
        # 🔴 铁律一：必须显式校园归属，不能指望 before_flush 回填（见 docstring）
        school_id=school_id,
        class_id=class_id,
        # 🔴 铁律二：档案 ↔ 账号硬锚点
        student_id=student_id,
        # 🔴 铁律三：由口令强度自动推导，调用方不得自选（SMP-24 根因）
        must_change_password=validate_password_strength(password) is not None,
    )
