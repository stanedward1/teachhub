from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Assignment(Base):
    """教师发布的上机作业任务。"""

    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    content = Column(Text, nullable=False)  # Markdown 正文
    deadline = Column(String(50))
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    short_name = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    attachments = relationship(
        "AssignmentAttachment",
        back_populates="assignment",
        cascade="all, delete-orphan",
        order_by="AssignmentAttachment.id",
    )


class AssignmentAttachment(Base):
    """教师布置任务时上传的附件（一对多）。"""

    __tablename__ = "assignment_attachments"

    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)  # 原始文件名（展示用）
    filepath = Column(String(500), nullable=False)  # 存储路径（/uploads/<filepath> 下载）
    created_at = Column(DateTime, server_default=func.now())

    assignment = relationship("Assignment", back_populates="attachments")


class Submission(Base):
    """学生的作业提交。"""

    __tablename__ = "submissions"

    # 一名学生在一份作业下只允许有一条提交：既是业务不变量，也是**并发双击**的兜底
    # ——应用层 `submit` 是「先查后改」，首次提交并发时两个请求可能双双查不到而各插一行；
    # 由该唯一索引拦下第二次，`submit` 捕获 IntegrityError 后退化为更新（返回 200 而非 409）。
    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "student_id", name="uq_submission_assignment_student"
        ),
    )

    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    # 指向 students.id（学生档案），与 scores/talks/performances 等业务表的 student_id 语义一致
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    content = Column(Text)
    filename = Column(String(255))
    filepath = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class ExcellentWork(Base):
    """教师评选的优秀作品。"""

    __tablename__ = "excellent_works"

    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, unique=True)
    selected_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    note = Column(Text)
    # 入选来源：manual（教师手工评选）/ ai_recommended（AI 推荐后由教师确认或自动入库）。
    # 与 selected_by（NOT NULL，始终记「执行入库的人」）配合，既区分来源又保留责任可追溯。
    source = Column(String(20), nullable=False, default="manual", server_default="manual")
    created_at = Column(DateTime, server_default=func.now())


class WorkComment(Base):
    """优秀作品下的评论互动。"""

    __tablename__ = "work_comments"

    id = Column(Integer, primary_key=True)
    excellent_id = Column(Integer, ForeignKey("excellent_works.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class SubmissionComment(Base):
    """教师对作业提交的点评（评语），直接挂在提交下。"""

    __tablename__ = "submission_comments"

    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    score = Column(Integer, nullable=True)  # 可选评分 0-100
    created_at = Column(DateTime, server_default=func.now())
