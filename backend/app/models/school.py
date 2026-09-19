from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(50), nullable=False, unique=True)
    address = Column(String(255))
    phone = Column(String(20))
    status = Column(String(20), nullable=False, default="active", server_default="active")  # active / disabled
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 平台超管创建人
    created_at = Column(DateTime, server_default=func.now())


class Classroom(Base):
    __tablename__ = "classrooms"
    # 班级编码校内唯一。原为全局唯一（unique=True），导致不同学校无法复用同一套编码
    # （如两所学校都有 "2024级计算机1班"），导入时会被误判为重复。
    __table_args__ = (
        UniqueConstraint("school_id", "code", name="uq_classroom_school_code"),
    )

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), nullable=False)
    major = Column(String(100))
    grade = Column(String(50))
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # 班主任
    is_graduated = Column(Boolean, nullable=False, default=False, server_default="0")  # 是否毕业
    created_at = Column(DateTime, server_default=func.now())


class ClassTeacher(Base):
    """班级-教师关联（科任老师）：除班主任外，允许多个教师共同管理一个班级。"""

    __tablename__ = "class_teachers"
    __table_args__ = (
        UniqueConstraint("class_id", "teacher_id", name="uq_class_teacher"),
    )

    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())


class Student(Base):
    __tablename__ = "students"
    # 学号校内唯一。原为全局唯一（unique=True），不同学校出现相同学号时会被误判为重复，
    # 而这在实际招生场景中完全正常（如各校都从 20240001 开始编号）。
    __table_args__ = (
        UniqueConstraint("school_id", "student_no", name="uq_student_school_no"),
    )

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    class_id = Column(Integer, ForeignKey("classrooms.id"), nullable=True, index=True)
    name = Column(String(50), nullable=False)
    gender = Column(String(10), default="男")
    birth_date = Column(Date)
    student_no = Column(String(50), nullable=False, index=True)
    major = Column(String(100))
    parent_name = Column(String(50))
    parent_phone = Column(String(20))
    student_type = Column(String(20), default="day")  # day 通学生 / boarding 寄宿生
    status = Column(String(20), default="active")
    is_dropped_out = Column(Boolean, nullable=False, default=False, server_default="0")  # 是否退学
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
