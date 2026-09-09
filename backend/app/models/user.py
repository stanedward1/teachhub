from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

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
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
