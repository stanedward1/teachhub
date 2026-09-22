from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, event
from sqlalchemy.sql import func

from app.database import Base

# 平台级作用域常量：`school_id` 为空的账号（平台超管）落在此作用域，全平台唯一。
PLATFORM_SCOPE = "platform"


def compute_username_scope(role: str | None, school_id: int | None, class_id: int | None) -> str:
    """计算用户名唯一性所属的「作用域键」（多租户安全的唯一性口径）。

    `username` 的语义随角色而变，因此唯一性口径也必须随角色分叉：

    - **学生**：`username` = 姓名，允许跨班重名 → 作用域 `stu:<school_id>:<class_id>`，
      只在**同校同班**内唯一；
    - **教师 / 学校管理员**：`username` = 登录名 → 作用域 `staff:<school_id>`，
      在**同校**内唯一（这正是此前缺失的那道约束）；
    - **平台超管**：`school_id` 为空 → 作用域 `platform`，全平台唯一。

    返回值恒为非空字符串，因此可以直接参与数据库唯一索引 —— 这是关键：
    不能像旧约束那样依赖 `class_id IS NULL`，因为在 MySQL / SQLite 中
    NULL 不参与唯一性判定，教师账号（class_id 为 NULL）会因此完全没有约束。

    ⚠️ 教师的作用域**只看 school_id，跟 class_id 无关**。班主任同步逻辑
    （`students_service._sync_head_teacher_class`）会给教师回填 `class_id`，
    若口径里混入 class_id，教师就会占用所属班级的命名空间，
    导致「同班出现与学生同名的新账号」这种误判。
    """
    if role == "student":
        return f"stu:{school_id or 0}:{class_id or 0}"
    if role in ("teacher", "school_admin"):
        return f"staff:{school_id}" if school_id is not None else PLATFORM_SCOPE
    # 未知角色一律按最严格口径（全平台唯一）处理，宁可误拒不可漏放。
    return PLATFORM_SCOPE


class User(Base):
    __tablename__ = "users"
    # 用户名唯一性由「作用域键 + username」的复合唯一约束在**数据库层**保证，
    # 覆盖所有账号创建路径（账号管理、学生建档、批量导入、自助注册、种子数据），
    # 应用层的「先查后插」只作为友好提示，不再承担唯一性保证（存在并发竞态）。
    __table_args__ = (
        UniqueConstraint("username_scope", "username", name="uq_user_scope_username"),
    )

    id = Column(Integer, primary_key=True)
    # 学生账号 username = 姓名（可重名），教师/管理员账号为登录名
    username = Column(String(50), nullable=False, index=True)
    # 用户名唯一性作用域键，由 before_insert / before_update 事件自动维护，
    # 业务代码不要手工赋值。nullable=False 是刻意设计：一旦某条写入路径漏算，
    # 会直接抛出非空约束错误而**不是**静默生成 NULL（NULL 会让唯一索引整体失效）。
    username_scope = Column(String(64), nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(50), nullable=False)
    # super_admin(平台超管) / school_admin(学校管理员) / teacher(教师) / student(学生)
    role = Column(String(20), nullable=False, default="student", index=True)
    avatar = Column(String(255))
    phone = Column(String(20))
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)  # 租户归属，super_admin 为 NULL
    class_id = Column(Integer, ForeignKey("classrooms.id"), nullable=True, index=True)
    # 安全策略：首次登录强制改密 + 登录失败锁定
    must_change_password = Column(Boolean, default=False, nullable=False)  # True=首次登录需改密
    failed_attempts = Column(Integer, default=0, nullable=False)           # 连续失败次数
    locked_until = Column(DateTime, nullable=True)           # 锁定截止时间
    # 会话版本号：改密 / 重置密码时 +1，使该账号此前签发的全部 access token 失效。
    # access token 是无状态 JWT 无法逐个撤销，只能靠版本号比对（见 app/deps.py）；
    # 与「撤销全部 refresh token」配套，才构成完整的改密即踢出所有设备。
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


@event.listens_for(User, "before_insert")
@event.listens_for(User, "before_update")
def _sync_username_scope(mapper, connection, target: User) -> None:
    """写入/更新前重算作用域键，保证唯一索引口径与业务语义始终一致。

    挂在 mapper 事件而非 Session 事件上，是为了覆盖所有 ORM 写入路径
    （`session.add` / 批量导入 / 种子数据）。租户中间件的 `before_flush`
    会先填好 `school_id`，本事件在其之后触发，因此能读到最终值。
    """
    target.username_scope = compute_username_scope(target.role, target.school_id, target.class_id)
