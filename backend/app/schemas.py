from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="教师=用户名，学生=姓名")
    password: str = Field(..., min_length=1, description="密码")
    class_id: Optional[int] = Field(None, description="学生登录时的班级 ID")
    school_id: Optional[int] = Field(None, description="学校 ID（教师/学校管理员/学生登录必填）")


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="学生姓名（作为用户名）")
    password: str = Field("123456", min_length=6, max_length=50, description="密码，默认 123456")
    class_id: Optional[int] = Field(None, description="班级 ID")


class PasswordRequest(BaseModel):
    old_password: str
    # 密码强度由 security.validate_password_strength 校验（至少8位+字母+数字）
    new_password: str = Field(..., min_length=1, max_length=50)


# ============ 成绩 ============
class ScoreCreate(BaseModel):
    student_id: int = Field(..., gt=0)
    subject: str = Field("未分类", max_length=50)
    score: float = Field(..., ge=0, le=150)
    exam_name: Optional[str] = None


class ScoreUpdate(BaseModel):
    student_id: Optional[int] = Field(None, gt=0)
    subject: Optional[str] = Field(None, max_length=50)
    score: Optional[float] = Field(None, ge=0, le=150)
    exam_name: Optional[str] = None


# ============ 请假 ============
class LeaveCreate(BaseModel):
    student_id: int = Field(..., gt=0)
    reason: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str = "登记"
    image: Optional[str] = None


class LeaveUpdate(BaseModel):
    reason: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None
    image: Optional[str] = None


# ============ 学生 ============
class StudentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    student_no: str = Field(..., min_length=1, max_length=50)
    class_id: Optional[int] = None
    gender: str = "男"
    birth_date: Optional[str] = None
    major: Optional[str] = None
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None
    student_type: str = "day"
    school_id: Optional[int] = None
    is_dropped_out: bool = False


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[str] = None
    class_id: Optional[int] = None
    major: Optional[str] = None
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None
    student_type: Optional[str] = None
    is_dropped_out: Optional[bool] = None


# ============ 班级日志 ============
class WorkLogCreate(BaseModel):
    date: Optional[str] = None
    content: str = ""


class ReturnRecordCreate(BaseModel):
    student_id: int = Field(..., gt=0)
    return_date: Optional[str] = None
    reason: Optional[str] = None
    note: Optional[str] = None


class TalkCreate(BaseModel):
    student_id: int = Field(..., gt=0)
    content: str = ""


# ============ 考勤 ============
class AttendanceRecord(BaseModel):
    student_id: int = Field(..., gt=0)
    status: str = "出勤"


class AttendanceCheckin(BaseModel):
    class_id: int = Field(..., gt=0)
    date: str = Field(..., min_length=1)
    records: list[AttendanceRecord] = Field(default_factory=list)

