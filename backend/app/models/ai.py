"""AI 批改相关模型：平台凭证（`ai_credentials`）与批改结果（`ai_grading_results`）。

设计要点（对应 docs/AI-GRADING-PRD.md）：

- **凭证表刻意不含 `school_id` 列**。凭证是平台资产，只有平台超管能配置与查看。
  不带 `school_id` 也就不会被 ORM 租户过滤器命中（`tenant.py::_tenant_models`
  只收集含 `school_id` 的映射类），因此在任何租户上下文下都可读 ——
  安全性由接口依赖 `require_super_admin` 保证，而**不是**靠查询过滤。
  这也顺带绕开了 `settings` 表存密钥的三个坑（明文返回 / 255 容量 / NULL 唯一失效）。
- **结果表带 `school_id`**：批改结果属于租户数据，由 ORM 事件自动回填与过滤，
  不需要、也不应手工拼 `school_id` 条件。
- `ai_key_encrypted` 存 Fernet 密文（见 `app/crypto.py`），读接口只回显掩码。
"""
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


# AI 批改结果的规范状态值（与 DB / API 契约逐字节一致；服务层一律引用这些常量，
# 避免散落的字面量拼错 —— 写错一个字母查询/判等就会静默失配）。
STATUS_PENDING = "pending"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"


class AiCredential(Base):
    """平台级 AI 服务凭证（兼容 OpenAI Chat Completions 协议的服务）。

    `updated_by` 记录最后修改凭证的超管，供审计追溯；凭证本身不做租户隔离，
    跨校共用一套，正是「平台统一接入、各校共享」的产品形态。
    """

    __tablename__ = "ai_credentials"

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False, default="deepseek")
    base_url = Column(String(255), nullable=False)
    model = Column(String(100), nullable=False)
    api_key_encrypted = Column(Text, nullable=False, default="")
    # 是否允许图片类附件按多模态（base64 data URL）送入，由超管按所配模型能力决定
    vision_enabled = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class AiGradingResult(Base):
    """AI 批改结果：一个提交一条（`submission_id` 唯一，重跑覆盖）。

    与教师评语（`submission_comments`）**并列存储、互不覆盖**：AI 结果只作参考，
    不写入、不修改教师评语与任何成绩字段。
    """

    __tablename__ = "ai_grading_results"

    id = Column(Integer, primary_key=True)
    submission_id = Column(
        Integer,
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    # 取值见上方 STATUS_PENDING / STATUS_SUCCESS / STATUS_FAILED 常量
    status = Column(String(20), nullable=False, default=STATUS_PENDING, index=True)
    provider = Column(String(50))
    model = Column(String(100))
    # 0-100，与 SubmissionComment.score 同量纲便于对照；可为空（模型未给出）
    score = Column(Integer, nullable=True)
    summary = Column(Text)  # 总评
    strengths = Column(Text)  # 亮点
    improvements = Column(Text)  # 改进建议
    raw_response = Column(Text)  # 原始响应，便于回溯与排障
    # 附件参与情况说明（如「已纳入附件：report.docx」/「图片附件未参与：多模态未启用」）
    attachment_used = Column(String(255))
    error = Column(Text)  # 失败原因；教师可见，学生端不展示
    # 优秀作品推荐（F4）：AI 候选 + 理由，教师确认后才写入 excellent_works
    is_excellent_candidate = Column(Boolean, nullable=False, default=False)
    excellent_reason = Column(Text)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class AiUsageDaily(Base):
    """AI 批改**每日调用计数**（平台级，跨租户；不含 `school_id`，故不受租户过滤）。

    为什么需要独立计数表：额度是平台级唯一成本刹车，必须按**实际外呼次数**统计。
    早先用「当日 `ai_grading_results` 行数」近似，有两个可绕过的漏洞：

    - 同一提交重跑走 `upsert`（覆盖同一行）⇒ 重复批改**不增加**计数；
    - 学生重交时 `_discard_ai_grading` 删掉结果行 ⇒ 当日计数**回退**。

    本表与结果行的生命周期彻底解耦：额度在**投递前原子预留**（见
    `ai_grading.reserve_quota`），因此计数只增不减，且并发批量触发不会超发。
    `day` 取自**数据库时钟**（`func.current_date()`），与写时间戳同一基准。

    🔴 DC-1 语义变更记录（2026-10，docs/DESIGN-AI校级能力.md §3 D2）：原文「额度刻意
    不分校」的决策由「AI 能力按平台/学校双维度开启 + 双维度额度池」需求推翻 ——
    本表仍是平台级唯一总刹车（**语义不变**），校级池作为**可选叠加层**由新表
    `AiUsageDailySchool` 承载（无校级配置 = 不写该表，双池双闸门）。
    """

    __tablename__ = "ai_usage_daily"
    # 显式命名唯一约束，与迁移 a9b8c7d6e5f4 建出的索引名保持一致（「迁移链 = 模型 schema」）
    __table_args__ = (UniqueConstraint("day", name="uq_ai_usage_daily_day"),)

    id = Column(Integer, primary_key=True)
    # 业务日（由数据库时钟决定）；唯一索引保证「一天一行」，也是并发首次创建的兜底
    day = Column(Date, nullable=False)
    # 当日已预留（≈ 已发生）的外呼次数
    call_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class AiUsageDailySchool(Base):
    """AI 批改【校级】每日调用计数（每校一天一行，可选叠加层）。

    语义（docs/DESIGN-AI校级能力.md §3 D2）：平台池（`AiUsageDaily`）仍是全平台
    唯一总刹车；本表是叠加其上的**校级护栏**，双池双闸门 —— 一次批改同时预留两池，
    任一不足即拒。无校级配置（settings 无 `school_ai_grading_daily_limit` 行）=
    不限 = **不写本表**（零 SQL、零行为变化，回归承诺见设计文档 §3 D7）。

    为什么独立成表而非与平台池共用一张表加 kind 列：kind 会把两池的行锁合并到同一
    物理行集，批改高峰时段同一 `(day, school_id)` 的批改与学伴预留互相阻塞，直接
    违背本项目「每池一表一把行锁、互不阻塞」的既定哲学（`models/companion.py`
    明文）。两表结构与既有四张池表风格完全一致。

    🔴 DC-1 语义变更记录（2026-10，docs/DESIGN-AI校级能力.md §3 D2）：原
    `AiUsageDaily` docstring 写明「额度刻意不分校」，由本次需求（AI 能力按平台/
    学校双维度开启 + 双维度额度池）推翻；平台池语义不变（总刹车），校级池为可选
    叠加层。本表即该变更的承载物。

    🔴 写入必须**显式赋 `school_id`**（铁律 #6；超管/教师上下文 `before_flush`
    不回填，实测见设计文档 §2.7 探针 [C]）。`school_id` **NOT NULL**：校池是学校
    维度的，必须显式赋值 —— `school_id is None` 的调用（历史脏数据作业）在代码层
    整段跳过校池逻辑，不触碰本表，模型层 `nullable=False` 兜底。

    唯一约束 `(day, school_id)`：`schools.id` 全局自增不跨校复用，无需把 school_id
    之外的租户列并入唯一键（与每生池 `(day, student_id)` 的取舍理由相同）。
    """

    __tablename__ = "ai_usage_daily_school"
    # 显式命名唯一约束，与迁移建出的约束名保持一致（「迁移链 = 模型 schema」）
    __table_args__ = (
        UniqueConstraint("day", "school_id", name="uq_ai_usage_daily_school_day_school"),
    )

    id = Column(Integer, primary_key=True)
    # 业务日（由数据库时钟决定）；唯一约束保证「一天一校一行」，也是并发首次创建的兜底
    day = Column(Date, nullable=False)
    # 租户归属：写入时必须显式赋值（见类 docstring，勿依赖 before_flush 回填）
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    # 当日已预留（≈ 已发生）的该校批改外呼次数
    call_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
