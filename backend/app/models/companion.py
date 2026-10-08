"""AI 学伴相关模型（docs/DESIGN-AI学伴.md）。

四张表，职责彼此独立：

1. ``ai_companion_conversations`` —— 会话（**一学生 × 一作业 = 一会话**）。
   带 ``school_id`` 参与 ORM 自动租户隔离；``(school_id, student_id, assignment_id)``
   唯一约束**结构性保证**「会话作用域」，不依赖前端自觉。
2. ``ai_companion_messages`` —— 会话消息（user / assistant 逐条落库）。
   ``school_id`` **冗余存一份**：单靠父会话可见性兜底，在**查询消息**时还要多做一次
   join；冗余后 ``select(AiCompanionMessage)`` 直接受 ORM 过滤器命中。冗余字段与父
   会话的一致性由 ``tenant.py`` 的 ``before_flush``（``assign_school_id``）自动回填，
   **不需要也不要手工赋值**。
3. ``ai_usage_daily_companion`` —— 学伴**独立**的每日调用计数（**平台池**，跨租户，
   **成本刹车**）。
   **刻意不含 ``school_id``**，与 ``ai_usage_daily`` 同口径：额度是平台级成本刹车，
   含了 ``school_id`` 会让每校各有一套额度，平台总花费变成 Σ（各校额度），刹车失效。
   （2026-10 注记：校级叠加层已由 ``AiUsageDailyCompanionSchool`` 承载，原「额度
   刻意不分校」决策被推翻，见该类 docstring 的 DC-1 变更记录。）
4. ``ai_companion_usage_daily_student`` —— 学伴**每生独立配额**的每日调用计数
   （docs/DESIGN-AI学伴配额.md D2，**公平**语义）。
   与平台池表**正交**、**叠加生效**（双闸门）。含 ``school_id`` 纳入租户隔离，但
   **写入显式赋值**（勿依赖 ``before_flush``，超管上下文落 NULL 就对租户不可见）。
   唯一约束 ``(day, student_id)``。

多租户说明（沿用设计文档 §9.1 的 S1–S3 约定）：

- 会话/消息表含 ``school_id``，查询时**不手写** ``school_id`` 条件，由 ORM 的
  ``do_orm_execute`` 自动注入；``tenant.py::_tenant_models`` 按**属性**收集模型，
  新增本模块自动纳入，无需改 ``tenant.py``。
- 平台池计数表（``ai_usage_daily_companion``）不含 ``school_id``，故不受租户过滤
  （平台级数据）。
- 每生配额表（``ai_companion_usage_daily_student``）含 ``school_id``，受 ORM 租户过滤
  管辖；写入时显式赋值（取父资源 ``student.school_id``）。

与 ``models/ai.py`` 的关系：`ai.py` 的 docstring 已限定为「AI 批改相关模型」，学伴是
**独立功能**，故单列本模块（而非塞进 `ai.py`）。
"""
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class AiCompanionConversation(Base):
    """学伴会话：一名学生在一份作业下只有一条会话。

    唯一约束含 ``school_id``（租户维度），对齐项目已有的「租户维度唯一约束」先例
    （迁移 ``a7b8c9d0e1f2``）：不含 ``school_id`` 时，跨校同 id 组合理论上可碰撞。
    """

    __tablename__ = "ai_companion_conversations"
    # 显式命名唯一约束，与迁移里建出的约束名保持一致（「迁移链 = 模型 schema」）
    __table_args__ = (
        UniqueConstraint(
            "school_id", "student_id", "assignment_id",
            name="uq_ai_companion_conv_scope",
        ),
    )

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    # 指向 students.id（学生档案），与 submissions/scores 等业务表的 student_id 语义一致
    student_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assignment_id = Column(
        Integer,
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 已完成问答的轮数（一次 ask = user + assistant 各一条 = turn_count += 1）
    turn_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class AiCompanionMessage(Base):
    """学伴会话中的单条消息（``role`` 为 ``user`` / ``assistant``）。

    排序取「最近 N 轮」时按 ``id`` 倒序（``id`` 单调，避免同秒并发下 ``created_at`` 不稳定）。
    """

    __tablename__ = "ai_companion_messages"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(
        Integer,
        ForeignKey("ai_companion_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 冗余的租户字段：使「查消息」直接受 ORM 租户过滤，无需 join 父会话
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    # 'user' | 'assistant'，与 OpenAI 协议对齐，可直接映射为 messages
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    # 是否命中护栏拒答（护栏命中率是产品护栏指标，需结构化计数而非读全文）
    refused = Column(Boolean, nullable=False, default=False, server_default="0")
    # 模型返回的结束原因（如 length = 被截断），用于排障
    finish_reason = Column(String(32), nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class AiUsageDailyCompanion(Base):
    """AI 学伴**独立**的每日调用计数（平台级，跨租户；不含 ``school_id``，故不受租户过滤）。

    与 ``models/ai.py::AiUsageDaily``（批改额度）**同构但相互独立**：两张表、两把行锁，
    互不阻塞。用途是学伴链路自己的成本刹车 —— 额度在**外呼前原子预留**（见
    ``ai_companion.reserve_companion_quota``），因此计数只增不减，且并发下不会超发。

    与批改额度 **不共用**（用户决策 DC-1）：语义是「两个独立的成本刹车」，物理隔离
    （两表两锁）是语义隔离最直接的实现。``day`` 取自**数据库时钟**
    （``func.current_date()``），与写时间戳同一基准。

    🔴 DC-1 语义变更记录（2026-10，docs/DESIGN-AI校级能力.md §3 D2）：原文「额度
    刻意不分校」（本表刻意不含 ``school_id``）的决策由「AI 能力按平台/学校双维度
    开启 + 双维度额度池」需求推翻 —— 本表仍是平台级唯一总刹车（**语义不变**），
    校级池作为**可选叠加层**由新表 ``AiUsageDailyCompanionSchool`` 承载（无校级
    配置 = 不写该表，与每生池构成三闸）。
    """

    __tablename__ = "ai_usage_daily_companion"
    # 显式命名唯一约束，与迁移里建出的约束名保持一致（「迁移链 = 模型 schema」）
    __table_args__ = (
        UniqueConstraint("day", name="uq_ai_usage_daily_companion_day"),
    )

    id = Column(Integer, primary_key=True)
    # 业务日（由数据库时钟决定）；唯一索引保证「一天一行」，也是并发首次创建的兜底
    day = Column(Date, nullable=False)
    # 当日已预留（≈ 已发生）的学伴外呼次数
    call_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class AiCompanionUsageDailyStudent(Base):
    """AI 学伴**每生独立配额**的每日调用计数（docs/DESIGN-AI学伴配额.md D2）。

    语义与平台池表 ``ai_usage_daily_companion`` **正交**：

    - 平台池 = 全平台一天总次数（**成本**语义，一行/天，跨租户）。
    - 本表 = 某学生一天可问次数（**公平**语义，一行/(天×学生)）。

    二者**叠加生效（双闸门）**，任一耗尽都拒绝提问（``ai_companion.ask``）。

    与平台池表的关键差异：

    - **含 ``school_id``**：每生配额是学生维度数据，纳入 ORM 自动租户隔离（同
      ``ai_companion_conversations.school_id``）。
      🔴 但**写入时显式取父资源（``student.school_id``）赋值**，不依赖
      ``tenant.py::before_flush`` 回填 —— 平台超管上下文（``school_id=None``）
      不会回填，落了 NULL 就对所有租户不可见。
    - **唯一约束 ``(day, student_id)``**：``student_id`` 全局唯一（``students.id`` 主键
      全局自增、不跨校复用），故不加 ``school_id`` 到唯一键；唯一约束自带索引，满足
      ``(day, student_id)`` 点查（配额预留的主路径）。
    - ``student_id`` 外键 ``ondelete="CASCADE"``：学生档案删除则配额行随之清理，避免孤儿。

    ``day`` 取自**数据库时钟**（``func.current_date()``，与平台池表同基准）。
    """

    __tablename__ = "ai_companion_usage_daily_student"
    # 显式命名唯一约束，与迁移里建出的约束名保持一致（「迁移链 = 模型 schema」）
    __table_args__ = (
        UniqueConstraint(
            "day", "student_id",
            name="uq_ai_companion_usage_daily_student",
        ),
    )

    id = Column(Integer, primary_key=True)
    # 业务日（由数据库时钟决定）；唯一约束保证「一天一生一行」，也是并发首次创建的兜底
    day = Column(Date, nullable=False)
    # 指向 students.id（学生档案），与 ai_companion_conversations.student_id 同语义
    student_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 租户归属：写入时必须显式赋值（见类 docstring，勿依赖 before_flush 回填）
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    # 当日已预留（≈ 已发生）的该生学伴外呼次数
    call_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class AiUsageDailyCompanionSchool(Base):
    """AI 学伴【校级】每日调用计数（每校一天一行，可选叠加层）。

    语义（docs/DESIGN-AI校级能力.md §3 D2）：平台池（`AiUsageDailyCompanion`）仍是
    全平台唯一总刹车；本表是叠加其上的**校级护栏** —— 学伴闸门从双闸（每生 → 平台）
    变为**三闸**（每生 → 学校 → 平台），任一不足即拒。无校级配置（settings 无
    `school_ai_companion_daily_limit` 行）= 不限 = **不写本表**（零 SQL、零行为
    变化，回归承诺见设计文档 §3 D7）。

    为什么独立成表而非与批改校池共用一张表加 kind 列：kind 会把两池的行锁合并到
    同一物理行集，批改高峰时段同一 `(day, school_id)` 的批改与学伴预留互相阻塞，
    直接违背本项目「每池一表一把行锁、互不阻塞」的既定哲学。与
    `models/ai.py::AiUsageDailySchool` **同构但相互独立**（两表两锁）。

    🔴 DC-1 语义变更记录（2026-10，docs/DESIGN-AI校级能力.md §3 D2）：原
    `AiUsageDailyCompanion` / 本模块 docstring 写明「额度刻意不分校」，由本次需求
    （AI 能力按平台/学校双维度开启 + 双维度额度池）推翻；平台池语义不变（总刹车），
    校级池为可选叠加层。本表即该变更的承载物。

    🔴 写入必须**显式赋 `school_id`**（铁律 #6；学生上下文虽带租户，但勿依赖
    `before_flush` 回填 —— 超管端点/后台线程上下文不回填，实测见设计文档 §2.7
    探针 [C]）。`school_id` **NOT NULL**：`school_id is None` 的调用（历史脏数据）
    在代码层整段跳过校池逻辑，不触碰本表，模型层 `nullable=False` 兜底。

    唯一约束 `(day, school_id)`：`schools.id` 全局自增不跨校复用，无需把 school_id
    之外的租户列并入唯一键（与每生池 `(day, student_id)` 的取舍理由相同）。
    """

    __tablename__ = "ai_usage_daily_companion_school"
    # 显式命名唯一约束，与迁移建出的约束名保持一致（「迁移链 = 模型 schema」）
    __table_args__ = (
        UniqueConstraint(
            "day", "school_id", name="uq_ai_usage_daily_companion_school_day_school"
        ),
    )

    id = Column(Integer, primary_key=True)
    # 业务日（由数据库时钟决定）；唯一约束保证「一天一校一行」，也是并发首次创建的兜底
    day = Column(Date, nullable=False)
    # 租户归属：写入时必须显式赋值（见类 docstring，勿依赖 before_flush 回填）
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False, index=True)
    # 当日已预留（≈ 已发生）的该校学伴外呼次数
    call_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
