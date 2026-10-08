from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="教师=用户名，学生=姓名")
    password: str = Field(..., min_length=1, description="密码")
    class_id: int | None = Field(None, description="学生登录时的班级 ID")
    school_id: int | None = Field(None, description="学校 ID（教师/学校管理员/学生登录必填）")


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="学生姓名（作为用户名）")
    # 去掉「默认 123456」：密码必须显式传入（缺省改为 422，不再静默使用弱口令）。
    # 强度不在 schema 层拒绝，而由 auth_service.register 复用 validate_password_strength
    # 判定，弱口令置 must_change_password=True 强制登录后修改（与教师建号口径一致）。
    password: str = Field(..., min_length=6, max_length=50, description="密码")
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


class StudentDeviceSetting(BaseModel):
    """平台级「学生单设备在线」开关请求体（平台超管）。

    student_single_device=True 时，学生每次登录都会作废该账号此前的全部会话
    （同一时间只能一台设备在线，后登录的挤掉先登录）；False 则恢复多设备并存。
    仅约束学生，教师 / 学校管理员 / 平台超管不受影响。
    """

    student_single_device: bool = Field(..., description="是否限制学生单设备在线")


class StudentBatchPassword(BaseModel):
    """学生批量改密请求体。

    与单个改密（`PUT /api/students/{id}/password`）语义一致：
    - `password` 缺省 / 空 ⇒ 重置为默认口令 `123456`；
    - 弱口令（不满足强度要求）会把 `must_change_password` 置 True，强制下次登录修改。

    `student_ids` 用 `max_length=500` 限幅，避免一次请求携带过多目标导致事务过长；
    前端多选跨页累计也远达不到这个量级。
    """

    student_ids: list[int] = Field(..., min_length=1, max_length=500, description="目标学生档案 ID 列表")
    password: str | None = Field(None, max_length=50, description="新密码；留空则重置为 123456")


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
    """平台级 AI 批改 / 学伴开关请求体（平台超管）。

    总开关为**平台级**（无按校粒度），因此 `daily_limit` 是唯一的成本刹车。

    AI 学伴（docs/DESIGN-AI学伴.md）复用本端点：新增 `companion_enabled` 与
    `companion_daily_limit`。学伴额度与批改额度**相互独立**（两个独立的成本刹车，
    见设计 §13.1 DC-1），故 `companion_daily_limit` 采用与 `daily_limit` 一致的
    `ge`/`le` 风格，缺省值 600（`settings.AI_COMPANION_DEFAULT_DAILY_LIMIT`）。
    """

    enabled: bool = Field(..., description="AI 批改总开关")
    auto_publish_excellent: bool = Field(
        False, description="优秀作品是否自动入库（默认候选制，需教师确认）"
    )
    daily_limit: int = Field(..., ge=1, le=100000, description="每日调用次数上限")
    max_tokens: int = Field(1200, ge=64, le=32000, description="单次调用 max_tokens 上限")
    companion_enabled: bool = Field(False, description="AI 学伴总开关（平台级，缺省关闭）")
    companion_daily_limit: int = Field(
        6000, ge=1, le=100000, description="AI 学伴每日调用次数上限（**平台池**；与批改额度、每生上限均相互独立）"
    )
    # 每个学生的每日次数上限（**每生独立配额**，docs/DESIGN-AI学伴配额.md D3）：
    # 与上方 companion_daily_limit（**全平台**总次数，成本刹车）语义/单位/量级都不同，
    # 二者**叠加生效（双闸门）**。
    # ⚠️ 风格取舍（设计 §5.3）：本字段**跟随既有 `companion_daily_limit` 的 `ge/le` 风格**
    # （带等价默认值 20）。硬约束 #3「不加 ge/le」针对**新增写接口**，本 schema 是既有的
    # `AiGradingSetting`，为不与既有字段冲突而保持一致；带默认值保住「字段缺省仍 200」。
    companion_per_student_daily_limit: int = Field(
        20, ge=1, le=100000, description="每个学生的 AI 学伴每日次数上限（与平台池 companion_daily_limit 不同）"
    )


class SchoolAiSetting(BaseModel):
    """校级 AI 能力配置请求体（平台超管专用，docs/DESIGN-AI校级能力.md §3 D5 / T04）。

    **部分更新三态语义**（判定必须用 `model_fields_set`，禁止 `if not body.x` ——
    那会把显式 `False`/`null` 误判成「未传」）：

    - 字段**未传** → 不动该配置；
    - 显式 **null** → 清除覆盖（删 school 级行：开关恢复跟随平台闸、上限恢复不限）；
    - 非空值 → 写入覆盖（开关写 `"1"`/`"0"`；上限写十进制字符串，`0` 合法）。

    🔴 铁律 #3：4 个字段全部带等价默认值 `None` ⇒ 空 body `{}` 也 200 且零变化；
    数值字段**不加 `ge`/`le`** —— 显式传入的数值（含 **bool 排除**：`bool` 是
    `int` 子类）在 service 层手工校验（负数 ⇒ 400，见 `ai_admin_service.set_school_ai_setting`）。
    既有的 `AiGradingSetting` 带 `ge/le` 是历史风格，本 schema 不跟随。
    """

    grading_enabled: bool | None = Field(None, description="本校 AI 批改开关；null=清除覆盖（跟随平台闸）")
    grading_daily_limit: int | None = Field(None, description="本校批改每日调用次数上限；null=不限")
    companion_enabled: bool | None = Field(None, description="本校 AI 学伴开关；null=清除覆盖（跟随平台闸）")
    companion_daily_limit: int | None = Field(None, description="本校学伴每日调用次数上限；null=不限")

    @field_validator("grading_daily_limit", "companion_daily_limit", mode="before")
    @classmethod
    def _reject_bool_for_limits(cls, v):
        """在类型转换**之前**拒绝 bool（⇒ 422）。

        🔴 Pydantic v2 lax 模式会把 `True`/`False` 强转成 `1`/`0`（`bool` 是 `int`
        子类），handler 层的 `isinstance(v, bool)` 检查将永远看不到 bool ——
        「bool 冒充数值」必须在进入类型转换前拦下（铁律 #3 的数值判定前移到
        schema 的 before 阶段；handler 内的检查保留作为 service 直调的防线）。
        """
        if isinstance(v, bool):
            raise ValueError("每日调用次数上限不能是布尔值，请传非负整数")
        return v


class AiCompanionAsk(BaseModel):
    """AI 学伴提问请求体（学生）。

    🔴 只接受 `question` 一个字段 —— 题干 / 历史 / 开关**一律由服务端自取**（D2），
    前端禁止传入（多传字段会被 Pydantic 忽略，但设计上明确不开放这些入口）。

    🔴 **类型校验铁律**：`question` **不加 `min_length` / `max_length`**，以保住
    「字段缺省仍 200 / 服务层空值仍 400」的既有口径 —— 空值/超长的具体判定（含
    **显式排除 `bool`**）在 service 层做，避免把「缺省」变成 422。
    """

    question: str | None = Field(None, description="学生本轮提问（1..1500 字）")


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


class PerformanceCreate(BaseModel):
    """学生表现登记请求体（`POST /api/performances`）。

    字段全部可选并带**等价默认值**，保持「缺省仍返回 200」的既有语义；
    仅做**类型**校验：`points` 非数字 → 422（原先会写库时抛 `DataError` → 500）。
    刻意不在 schema 层加取值范围 —— 默认分值由服务层按类型决定（积极 +1 / 消极 -1），
    保持原语义不变。
    """

    student_id: int | None = Field(None, description="学生 ID")
    ptype: str | None = Field("积极", description="表现类型：积极 / 消极")
    content: str | None = Field("", description="表现内容")
    points: int | None = Field(None, description="积分；留空按类型默认（积极 +1 / 消极 -1）")
    image: str | None = Field(None, description="关联图片路径")


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


# ============ 作业提交 ============
class SubmissionCreate(BaseModel):
    """学生提交作业请求体（`POST /api/homework/assignments/{id}/submissions`）。

    原先路由用裸 `payload: dict`，带来两个问题（见
    `docs/REVIEW-2026-09-25-code-audit.md` P0-A，均已探针实证）：
    ① `filepath` 未做**路径安全**校验，穿越路径会一路带到「重交时删旧附件」与
       「附件抽取读盘」，学生即可删除/读取上传目录之外的任意文件；
    ② `content` 传非字符串时 `(x or "").strip()` 抛 AttributeError → 500。

    本模型只做**类型**校验 + **路径安全**校验：
    - 字段全部可选并带**等价默认值**，保持「缺省仍 200」的既有语义；
    - `filepath` 允许上传目录内的相对路径（含 `not/exist/missing.pdf` 这类子目录形态，
      以保证「附件缺失」仍走 200 + 说明文案），**只拒绝逃出上传目录**的路径（→ 422）。
    """

    content: str | None = Field("", description="作业正文")
    filename: str | None = Field(None, description="附件原始文件名")
    filepath: str | None = Field(None, description="附件相对路径（必须位于上传目录内）")

    @field_validator("filepath")
    @classmethod
    def _validate_filepath(cls, v):
        if v is None or not str(v).strip():
            return v
        from app.uploads import resolve_upload_path

        try:
            resolve_upload_path(v)
        except ValueError as exc:
            raise ValueError("文件路径非法：只能引用上传目录内的文件") from exc
        return v


class SubmissionCommentCreate(BaseModel):
    """教师作业点评请求体（`POST /api/homework/submissions/{id}/comments`）。

    字段可选并带**等价默认值**，保持「缺省仍可提交、由服务层判空返回 400」的语义；
    仅做**类型**校验：`score` 非数字 → 422（原先服务层 `int()` 抛 `ValueError` → 500）。
    0-100 范围校验保留在服务层，此处刻意不加 `ge`/`le`，以免把既有的 400 变成 422。
    """

    content: str | None = Field("", description="点评内容")
    score: int | None = Field(None, description="可选评分（0-100）")


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

