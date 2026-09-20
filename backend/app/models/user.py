from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"
    # 学生账号 username = 姓名，允许跨班重名；此处只约束「同班不重复」，
    # 避免同一班级出现两个同名账号导致登录歧义。
    # class_id 为 NULL 的教师/管理员不受此约束（MySQL 中 NULL 不参与唯一性判定），
    # 其账号唯一性仍由应用层保证。
    __table_args__ = (
        UniqueConstraint("class_id", "username", name="uq_user_class_username"),
    )

    id = Column(Integer, primary_key=True)
    # 学生账号 username = 姓名（可重名），教师/管理员账号学校内唯一
    username = Column(String(50), nullable=False, index=True)
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
    # 最后登录留痕：管理员/班主任据此判断账号是否异常地点登录（学生管理处的「最后登录」列）
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)        # 长度 45 兼容 IPv6 完整写法
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
