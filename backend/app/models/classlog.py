from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class WorkLog(Base):
    """班主任每日工作日志。"""

    __tablename__ = "work_logs"

    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    date = Column(Date)
    content = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class ClassPlan(Base):
    """班级工作计划与总结。"""

    __tablename__ = "class_plans"

    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    plan_type = Column(String(20), default="计划")  # 计划 / 总结
    content = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class TeacherPlan(Base):
    """班主任个人工作计划与总结。"""

    __tablename__ = "teacher_plans"

    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    plan_type = Column(String(20), default="计划")
    content = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class Schedule(Base):
    """课程表。"""

    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    day_of_week = Column(Integer, nullable=False)  # 1-5
    period = Column(Integer, nullable=False)  # 第几节 1-8
    subject = Column(String(50))
    teacher_name = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())


class Activity(Base):
    """班级活动记录。"""

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    filepath = Column(Text)  # 多张配图路径，JSON 数组字符串（兼容旧单值字符串）
    created_at = Column(DateTime, server_default=func.now())


class Talk(Base):
    """师生谈心记录。"""

    __tablename__ = "talks"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    content = Column(Text)
    images = Column(Text)  # 多张配图路径，JSON 数组字符串
    created_at = Column(DateTime, server_default=func.now())


class ReturnRecord(Base):
    """学生返校记录。"""

    __tablename__ = "return_records"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    return_date = Column(Date)
    reason = Column(String(255))
    note = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class Performance(Base):
    """学生表现记录（积极/消极）。"""

    __tablename__ = "performances"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    ptype = Column(String(20), default="积极")  # 积极 / 消极
    points = Column(Integer, default=1)  # 分值：正数加分、负数减分，默认 积极+1/消极-1
    content = Column(Text)
    image = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())


class StudentComment(Base):
    """学生评语。"""

    __tablename__ = "student_comments"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    content = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
