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


class RegistrationSetting(BaseModel):
    """平台级「学生自助注册」总开关请求体（平台超管）。

    allow_registration=True 开放注册；False 关闭注册（登录页隐藏入口 + 后端拒绝注册）。
    """

    allow_registration: bool = Field(..., description="是否开放学生自助注册")


class AiCredentialSetting(BaseModel):
    """平台级 AI 服务凭证请求体（平台超管）。

    只写不回显：`api_key` 留空表示「保持原密钥不变」，读接口永远只返回掩码。
    """

    provider: str = Field("deepseek", max_length=50, description="服务商标识（仅作展示）")
    base_url: str = Field(
        ..., min_length=1, max_length=255, description="服务地址，如 https://api.deepseek.com"
    )
    model: str = Field(..., min_length=1, max_length=100, description="模型名，如 deepseek-chat")
    api_key: str | None = Field(None, max_length=500, description="API Key；留空表示不修改")
    vision_enabled: bool | None = Field(None, description="是否让图片附件按多模态送入；留空则由服务商与模型自动推断")
    enabled: bool = Field(True, description="该凭证是否启用")


class AiGradingSetting(BaseModel):
    """平台级 AI 批改开关请求体（平台超管）。

    总开关为**平台级**（无按校粒度），因此 `daily_limit` 是唯一的成本刹车。
    """

    enabled: bool = Field(..., description="AI 批改总开关")
    auto_publish_excellent: bool = Field(
        False, description="优秀作品是否自动入库（默认候选制，需教师确认）"
    )
    daily_limit: int = Field(..., ge=1, le=100000, description="每日调用次数上限")
    max_tokens: int = Field(1200, ge=64, le=32000, description="单次调用 max_tokens 上限")


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


# ============ 刷新令牌（F3） ============
class RefreshRequest(BaseModel):
    """刷新 / 登出请求体：携带登录或刷新接口返回的长期刷新令牌。

    不加最小长度约束：空串 / 无效令牌统一走「按 hash 未命中 → 401」分支，
    与刷新接口的错误语义保持一致。
    """

    refresh_token: str

