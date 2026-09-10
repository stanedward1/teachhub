from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="教师=用户名，学生=姓名")
    password: str = Field(..., min_length=1, description="密码")
    class_id: int | None = Field(None, description="学生登录时的班级 ID")
    school_id: int | None = Field(None, description="学校 ID（教师/学校管理员/学生登录必填）")


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="学生姓名（作为用户名）")
    password: str = Field("123456", min_length=6, max_length=50, description="密码，默认 123456")
    class_id: int | None = Field(None, description="班级 ID")


class PasswordRequest(BaseModel):
    old_password: str
    # 密码强度由 security.validate_password_strength 校验（至少8位+字母+数字）
    new_password: str = Field(..., min_length=1, max_length=50)


# ============ 成绩 ============
class ScoreCreate(BaseModel):
    student_id: int = Field(..., gt=0)
    subject: str = Field("未分类", max_length=50)
    score: float = Field(..., ge=0, le=150)
    exam_name: str | None = None


class ScoreUpdate(BaseModel):
    student_id: int | None = Field(None, gt=0)
    subject: str | None = Field(None, max_length=50)
    score: float | None = Field(None, ge=0, le=150)
    exam_name: str | None = None


# ============ 请假 ============
class LeaveCreate(BaseModel):
    student_id: int = Field(..., gt=0)
    reason: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    status: str = "登记"
    image: str | None = None


class LeaveUpdate(BaseModel):
    reason: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    status: str | None = None
    image: str | None = None


# ============ 学生 ============
class StudentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    student_no: str = Field(..., min_length=1, max_length=50)
    class_id: int | None = None
    gender: str = "男"
    birth_date: str | None = None
    major: str | None = None
    parent_name: str | None = None
    parent_phone: str | None = None
    student_type: str = "day"
    school_id: int | None = None
    is_dropped_out: bool = False


class StudentUpdate(BaseModel):
    name: str | None = None
    gender: str | None = None
    birth_date: str | None = None
    class_id: int | None = None
    major: str | None = None
    parent_name: str | None = None
    parent_phone: str | None = None
    student_type: str | None = None
    is_dropped_out: bool | None = None


# ============ 班级日志 ============
class WorkLogCreate(BaseModel):
    date: str | None = None
    content: str = ""


class ReturnRecordCreate(BaseModel):
    student_id: int = Field(..., gt=0)
    return_date: str | None = None
    reason: str | None = None
    note: str | None = None


class TalkCreate(BaseModel):
    student_id: int = Field(..., gt=0)
    content: str = ""
    images: list[str] | None = None


# ============ 家校沟通 ============
class CommunicationCreate(BaseModel):
    student_id: int = Field(..., gt=0, description="学生 ID")
    method: str = Field("电话", max_length=20, description="沟通方式：电话/微信/面谈/其他")
    content: str = Field("", description="沟通内容（支持 Markdown 图文混排）")
    feedback: str = Field("", description="家长反馈")


# ============ 教学资源 ============
class ResourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="资源名称")
    category: str = Field("其他", max_length=50)
    filename: str | None = None
    filepath: str | None = None


# ============ 试卷 ============
class ExamUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    exam_type: str | None = Field(None, max_length=50)


# ============ 座位表 ============
class SeatSave(BaseModel):
    class_id: int = Field(..., gt=0, description="班级 ID")
    layout: list = Field(default_factory=list, description="座位布局二维数组")
    columns: int = Field(6, ge=1, le=20)


# ============ 周报 ============
class ReportSave(BaseModel):
    id: int | None = Field(None, description="周报 ID，传入则更新，否则新建")
    title: str = Field(..., min_length=1, max_length=200)
    class_id: int | None = None
    content: str = ""
    week_start: str | None = None
    week_end: str | None = None
    data_snapshot: dict = Field(default_factory=dict)


# ============ 学生标签 ============
class StudentTagCreate(BaseModel):
    tag: str = Field(..., min_length=1, max_length=50, description="标签文本")
    category: str = Field("自定义", max_length=20, description="学业/品德/技能/自定义")


# ============ 考勤 ============
class AttendanceRecord(BaseModel):
    student_id: int = Field(..., gt=0)
    status: str = "出勤"


class AttendanceCheckin(BaseModel):
    class_id: int = Field(..., gt=0)
    date: str = Field(..., min_length=1)
    records: list[AttendanceRecord] = Field(default_factory=list)


# ============================================================
# 响应模型（Out）：补全 OpenAPI 文档与响应序列化校验。
# 使用 from_attributes=True 使 ORM 对象可直接被 response_model 序列化；
# 字段均为可选，避免与 to_dict 返回的实际字段不一致导致校验报错。
# ============================================================

class _ORMOut(BaseModel):
    """响应模型基类：允许从 ORM 对象直接取值，并忽略未知字段。"""
    model_config = ConfigDict(from_attributes=True, extra="ignore")


class ScoreOut(_ORMOut):
    id: int | None = None
    student_id: int | None = None
    subject: str | None = None
    score: float | None = None
    exam_name: str | None = None
    created_at: str | None = None
    # 序列化时由 audit.attach_student 附加
    student_name: str | None = None
    student_no: str | None = None


class LeaveOut(_ORMOut):
    id: int | None = None
    student_id: int | None = None
    reason: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    status: str | None = None
    image: str | None = None
    created_at: str | None = None
    student_name: str | None = None
    student_no: str | None = None


class CommunicationOut(_ORMOut):
    id: int | None = None
    student_id: int | None = None
    method: str | None = None
    content: str | None = None
    feedback: str | None = None
    created_at: str | None = None
    student_name: str | None = None
    student_no: str | None = None


class StudentOut(_ORMOut):
    id: int | None = None
    name: str | None = None
    student_no: str | None = None
    gender: str | None = None
    class_id: int | None = None
    major: str | None = None
    parent_name: str | None = None
    parent_phone: str | None = None
    student_type: str | None = None
    is_dropped_out: bool | None = None


class ClassroomOut(_ORMOut):
    id: int | None = None
    name: str | None = None
    code: str | None = None
    major: str | None = None
    grade: str | None = None
    teacher_id: int | None = None
    is_graduated: bool | None = None


class SchoolOut(_ORMOut):
    id: int | None = None
    name: str | None = None


class PerformanceOut(_ORMOut):
    id: int | None = None
    student_id: int | None = None
    ptype: str | None = None
    content: str | None = None
    points: int | None = None
    created_at: str | None = None
    student_name: str | None = None
    student_no: str | None = None


class TalkOut(_ORMOut):
    id: int | None = None
    student_id: int | None = None
    teacher_id: int | None = None
    content: str | None = None
    images: list[str] | None = None
    created_at: str | None = None
    student_name: str | None = None
    student_no: str | None = None


class ReturnRecordOut(_ORMOut):
    id: int | None = None
    student_id: int | None = None
    return_date: str | None = None
    reason: str | None = None
    note: str | None = None
    created_at: str | None = None
    student_name: str | None = None
    student_no: str | None = None


class StudentCommentOut(_ORMOut):
    id: int | None = None
    student_id: int | None = None
    content: str | None = None
    created_at: str | None = None
    student_name: str | None = None
    student_no: str | None = None


class AttendanceOut(_ORMOut):
    id: int | None = None
    class_id: int | None = None
    student_id: int | None = None
    date: str | None = None
    status: str | None = None


class WorkLogOut(_ORMOut):
    id: int | None = None
    teacher_id: int | None = None
    date: str | None = None
    content: str | None = None


class UserOut(_ORMOut):
    id: int | None = None
    username: str | None = None
    name: str | None = None
    role: str | None = None
    avatar: str | None = None
    phone: str | None = None
    school_id: int | None = None
    class_id: int | None = None
    must_change_password: bool | None = None

