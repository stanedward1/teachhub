from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class Score(Base):
    """学生成绩。"""

    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    subject = Column(String(50), nullable=False)
    score = Column(Float, nullable=False)
    exam_name = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Leave(Base):
    """请假/考勤记录。"""

    __tablename__ = "leaves"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    reason = Column(String(255))
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String(20), default="登记")  # 登记 / 已销假
    image = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Point(Base):
    """学生积分（正/负），可关联学生表现记录。"""

    __tablename__ = "points"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    points = Column(Integer, nullable=False, default=0)
    reason = Column(String(255))
    performance_id = Column(Integer, ForeignKey("performances.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Communication(Base):
    """家校沟通记录。"""

    __tablename__ = "communications"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    method = Column(String(20), default="电话")  # 电话/微信/面谈/其他
    content = Column(Text)
    feedback = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Resource(Base):
    """教学资源。"""

    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    category = Column(String(50), default="其他")
    filename = Column(String(255))
    filepath = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Exam(Base):
    """试卷（支持文件上传）。"""

    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    exam_type = Column(String(50), default="单元测验")
    content = Column(Text)
    filename = Column(String(255))
    filepath = Column(String(500))
    filesize = Column(Integer, default=0)
    filetype = Column(String(20))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Seat(Base):
    """座位表布局（JSON 存储）。"""

    __tablename__ = "seats"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False, unique=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    layout = Column(Text)  # JSON: [[student_id, ...], ...]
    columns = Column(Integer, default=6)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Setting(Base):
    """系统设置（键值对，如当前年级），按学校隔离（校内 key 唯一）。"""

    __tablename__ = "settings"
    __table_args__ = (
        UniqueConstraint("school_id", "key", name="uq_settings_school_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    key = Column(String(50), index=True, nullable=False)
    value = Column(String(255))


class ImportHistory(Base):
    """数据导入历史记录。"""

    __tablename__ = "import_history"

    id = Column(Integer, primary_key=True, index=True)
    import_type = Column(String(20), nullable=False, index=True)  # student / score
    filename = Column(String(255), nullable=False)
    total_rows = Column(Integer, default=0)
    success_rows = Column(Integer, default=0)
    error_rows = Column(Integer, default=0)
    errors = Column(Text)  # JSON 格式错误详情
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StudentProfileTag(Base):
    """学生数字画像标签（教师自定义）。"""

    __tablename__ = "student_profile_tags"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    tag = Column(String(50), nullable=False)  # 标签文本
    category = Column(String(20), default="自定义")  # 学业/品德/技能/自定义
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WeeklyReport(Base):
    """班级周报/月报。"""

    __tablename__ = "weekly_reports"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    week_start = Column(Date)
    week_end = Column(Date)
    content = Column(Text)
    data_snapshot = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class StudentBoardHistory(Base):
    """学生寄宿/通学状态变更历史。"""

    __tablename__ = "student_board_history"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    old_type = Column(String(20))  # day / boarding
    new_type = Column(String(20), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Attendance(Base):
    """学生每日考勤点名记录。"""

    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("class_id", "student_id", "date", name="uq_attendance_student_date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    date = Column(Date, nullable=False, index=True)  # YYYY-MM-DD
    status = Column(String(20), default="出勤")  # 出勤 / 缺勤 / 请假 / 迟到
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
