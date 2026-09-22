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
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


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
    # pending（已排队/进行中） / success / failed
    status = Column(String(20), nullable=False, default="pending")
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
