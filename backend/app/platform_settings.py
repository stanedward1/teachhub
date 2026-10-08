"""平台级全局配置读写工具。

作用域约定
----------
`settings` 表以 `school_id` 区分作用域：

- `school_id` 为具体学校 id → **校内配置**（校内 key 唯一，见 `uq_settings_school_key`）；
- `school_id IS NULL` → **平台级全局配置**（跨校生效，由平台超管维护）。

本模块只读写全局作用域（`school_id IS NULL`）的配置行，供认证模块（学生注册开关）、
AI 批改开关与平台超管接口复用；校内配置请勿使用本模块（校内配置由 `routers/admin.set_setting`
以 `user.school_id` 定位）。

⚠️ 查询必须绕过 ORM 租户过滤（2026-09-22 修）
-------------------------------------------
全局配置行的 `school_id` 就是 NULL，而 ORM 的 `do_orm_execute` 事件会为**每一个**含
`school_id` 列的模型注入 `school_id = 当前租户`。两者相与恒为假 —— 也就是说，
在**带租户上下文**的请求里（例如学生提交作业时读 AI 总开关），不加处理地查全局配置
**永远查不到**，会静默落回默认值。

因此本模块所有查询都显式带 `execution_options(skip_tenant_filter=True)`
（该开关由 `app/tenant.py` 识别）。这是「平台级配置」这一语义的必然要求：
它本就该跨租户读取，不应受调用方所处租户影响。

默认值策略
----------
读取缺失的配置项时返回调用方传入的 `default`（而非抛错），保证「配置行不存在」与
「配置项从未被设置过」两种情形下行为可预期。默认值取向按功能分别约定：

- 学生自助注册开关 `allow_registration` 缺省视为 **True**（保持引入开关之前的历史行为，向后兼容）；
- 学生「单设备在线」开关 `student_single_device` 缺省视为 **True**（产品要求「后登录挤掉先登录」，
  开启才符合预期行为；关闭是为了留运维退路，例如联调时需同时保留多个学生会话）；
- AI 批改相关开关缺省一律 **False**（新功能默认不产生费用、不改动既有流程）。
"""
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Setting

# 学生自助注册总开关的全局配置键（school_id IS NULL）
ALLOW_REGISTRATION_KEY = "allow_registration"

# 学生「单设备在线」开关的全局配置键（school_id IS NULL）
# 开启时：学生每次登录都会作废该账号此前的全部会话（后登录挤掉先登录）。
STUDENT_SINGLE_DEVICE_KEY = "student_single_device"

# ---------------- AI 批改相关全局配置键 ----------------
# 平台级总开关：关闭时不产生任何外呼（缺省关闭）
AI_GRADING_ENABLED_KEY = "ai_grading_enabled"
# 优秀作品自动入库开关（缺省关闭）：开启后 AI 推荐的优秀作品无需教师逐条确认
AI_AUTO_PUBLISH_EXCELLENT_KEY = "ai_auto_publish_excellent"
# 「开启自动入库的人」（平台超管 user id）：自动入库时计入 excellent_works.selected_by
AI_AUTO_PUBLISH_OWNER_KEY = "ai_auto_publish_owner"
# 每日调用次数上限（成本护栏；总开关为平台级，限额是唯一的成本刹车）
AI_DAILY_LIMIT_KEY = "ai_daily_call_limit"
# 单次调用 max_tokens 上限
AI_MAX_TOKENS_KEY = "ai_max_tokens"

# ---------------- AI 学伴相关全局配置键（docs/DESIGN-AI学伴.md） ----------------
# 平台级总开关：关闭时不产生任何外呼（缺省关闭）
AI_COMPANION_ENABLED_KEY = "ai_companion_enabled"
# 学伴**独立**每日调用次数上限（与批改的 `ai_daily_call_limit` 相互独立，两个刹车各管一条链路）
AI_COMPANION_DAILY_LIMIT_KEY = "ai_companion_daily_limit"
# 学伴**每个学生**每日次数上限（docs/DESIGN-AI学伴配额.md D3，与上方**平台池** key 语义
# 不同、量级不同、并存不覆盖 —— 复用一个 key 会让两者互相覆盖，是灾难性的配置 bug）。
AI_COMPANION_PER_STUDENT_DAILY_LIMIT_KEY = "ai_companion_per_student_daily_limit"

# 视为「真」/「假」的字符串取值（比较前忽略大小写并去除首尾空白）
_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def get_global_setting(db: Session, key: str, default: str | None = None) -> str | None:
    """读取平台级全局配置（`school_id IS NULL`）。

    Args:
        db: 数据库会话。
        key: 配置键。
        default: 配置行不存在时返回的默认值。

    Returns:
        配置的字符串值；不存在时返回 `default`。
    """
    row = (
        db.query(Setting)
        .execution_options(skip_tenant_filter=True)
        .filter(Setting.school_id.is_(None), Setting.key == key)
        .first()
    )
    return row.value if row else default


def set_global_setting(db: Session, key: str, value: str) -> Setting:
    """写入平台级全局配置（`school_id IS NULL`）：存在则更新，不存在则新建。

    Args:
        db: 数据库会话。
        key: 配置键。
        value: 配置值（字符串）。

    Returns:
        被更新的 `Setting` 实例。

    Note:
        仅执行 `db.add` / 字段赋值，**不 commit**，由调用方统一提交并记录审计，
        以保证「配置写入 + 审计日志」在同一事务内原子提交。

    Warning:
        本函数为**平台超管路径**设计（超管 `school_id` 为 NULL，ORM 的 `before_flush`
        不会改写新建行的 `school_id`）。若在校内租户上下文里调用，`tenant.py` 的
        `assign_school_id` 会把新建行填成该租户，从而**变成校内配置**。
    """
    row = (
        db.query(Setting)
        .execution_options(skip_tenant_filter=True)
        .filter(Setting.school_id.is_(None), Setting.key == key)
        .first()
    )
    if row:
        row.value = value
    else:
        row = Setting(school_id=None, key=key, value=value)
        db.add(row)
    return row


def _is_truthy(value: str | None) -> bool:
    """字符串布尔解析：`"1"/"true"/"yes"/"on"`（忽略大小写、strip）为 True。"""
    return (value or "").strip().lower() in _TRUTHY


def to_bool(value: str | None, default: bool = False) -> bool:
    """全局配置的布尔解析：真值集→True、假值集→False，其余（含缺省）取 `default`。"""
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    return default


def _as_positive_int(value: str | None, default: int) -> int:
    """解析正整数配置；非法值或非正数一律回落 `default`（避免误配成 0 停摆）。"""
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def is_registration_allowed(db: Session) -> bool:
    """学生自助注册是否开放。

    判定规则：

    - 配置缺失（全新库、尚未初始化）→ **True**（保持历史默认行为，向后兼容）；
    - 取值属于 `1 / true / yes / on`（忽略大小写、strip）→ True；
    - 其余取值（如 `0 / false / off`）→ False。

    Args:
        db: 数据库会话。

    Returns:
        是否允许学生自助注册。
    """
    value = get_global_setting(db, ALLOW_REGISTRATION_KEY, default=None)
    if value is None:
        return True
    return _is_truthy(value)


def is_student_single_device_enabled(db: Session) -> bool:
    """学生「单设备在线」是否开启（平台级，缺省**开启**）。

    开启时，学生每次登录都会作废该账号此前的**全部**会话（access + refresh），即
    「同一时间只能一台设备在线，后登录的会把先登录的挤下去」。教师 / 学校管理员 /
    平台超管**不受**该开关约束（可与学生在多设备同时在线）。

    与 `is_registration_allowed` 的关键差异：那里是「配置缺失 ⇒ True」的**向后兼容**
    特例，这里走通用的 `to_bool(default=True)`，因此**显式写入的假值集**
    （`0 / false / no / off`）同样能关闭它 —— 运维需要的是「一键关掉」退路，
    不能被「缺省 True」的实现细节吃掉。

    Args:
        db: 数据库会话。

    Returns:
        是否启用学生单设备在线限制。
    """
    return to_bool(get_global_setting(db, STUDENT_SINGLE_DEVICE_KEY), default=True)


def is_ai_grading_enabled(db: Session) -> bool:
    """AI 批改总开关（平台级，缺省**关闭**）。

    关闭时不产生任何外呼 —— 调用方应在发起批改前先用本函数短路。
    """
    return to_bool(get_global_setting(db, AI_GRADING_ENABLED_KEY), default=False)


def is_ai_auto_publish_enabled(db: Session) -> bool:
    """优秀作品是否「自动入库」（缺省**关闭**：推荐只作候选，需教师确认）。"""
    return to_bool(get_global_setting(db, AI_AUTO_PUBLISH_EXCELLENT_KEY), default=False)


def get_ai_auto_publish_owner(db: Session) -> int | None:
    """开启自动入库的超管 user id（用于自动入库时写 `excellent_works.selected_by`）。

    `selected_by` 为 NOT NULL，自动入库也必须记一个「执行入库的人」：
    记开启该配置的超管，配置本身即其授权凭据。
    """
    value = get_global_setting(db, AI_AUTO_PUBLISH_OWNER_KEY)
    return _as_positive_int(value, 0) or None


def get_ai_daily_limit(db: Session) -> int:
    """每日调用次数上限（成本护栏），缺省取 `settings.AI_DEFAULT_DAILY_LIMIT`。"""
    return _as_positive_int(
        get_global_setting(db, AI_DAILY_LIMIT_KEY), settings.AI_DEFAULT_DAILY_LIMIT
    )


def get_ai_max_tokens(db: Session) -> int:
    """单次调用 max_tokens 上限，缺省取 `settings.AI_DEFAULT_MAX_TOKENS`。"""
    return _as_positive_int(
        get_global_setting(db, AI_MAX_TOKENS_KEY), settings.AI_DEFAULT_MAX_TOKENS
    )


def is_ai_companion_enabled(db: Session) -> bool:
    """AI 学伴总开关（平台级，缺省**关闭**）。

    关闭时不产生任何外呼 —— 调用方应在发起学伴提问前先用本函数短路。

    Note:
        内部经 `get_global_setting` 读取，而该函数已带 `execution_options(
        skip_tenant_filter=True)`。**这是必须的**：学生请求带租户上下文，全局配置行
        （`school_id IS NULL`）会被 ORM 的 `do_orm_execute` 注入 `school_id = 当前租户`
        而与 NULL 相与恒为假，不加处理地查询**永远查不到**，会**静默**落回默认 False
        且**不报错** —— 表面现象是「超管明明开了，学生按钮死活不出现」，极难排查。
        详见模块 docstring 与 `get_global_setting` 的说明。
    """
    return to_bool(get_global_setting(db, AI_COMPANION_ENABLED_KEY), default=False)


def get_ai_companion_daily_limit(db: Session) -> int:
    """学伴每日调用次数上限（成本护栏），缺省取 `settings.AI_COMPANION_DEFAULT_DAILY_LIMIT`。

    与批改的 `get_ai_daily_limit` **同口径但相互独立**：DB 中的
    `ai_companion_daily_limit` 覆盖 config 缺省值，非法值（非正整数）回落缺省，
    避免误配成 0 导致功能停摆。学伴链路使用独立的计数表，两套额度互不挤占。
    """
    return _as_positive_int(
        get_global_setting(db, AI_COMPANION_DAILY_LIMIT_KEY),
        settings.AI_COMPANION_DEFAULT_DAILY_LIMIT,
    )


def get_ai_companion_per_student_daily_limit(db: Session) -> int:
    """学伴**每个学生**每日次数上限（公平护栏），缺省取
    `settings.AI_COMPANION_DEFAULT_PER_STUDENT_DAILY_LIMIT`。

    与 `get_ai_companion_daily_limit`（**平台池**，成本护栏）**并存且相互独立**：
    DB 中的 `ai_companion_per_student_daily_limit` 覆盖 config 缺省值，非法值
    （非正整数）回落缺省，避免误配成 0 导致所有学生无法提问。

    🔴 内部经 `get_global_setting`（自带 `skip_tenant_filter=True`）读取。**这是必须的**：
    学生请求带租户上下文，全局配置行（`school_id IS NULL`）会被 ORM 注入
    `school_id = 当前租户` 而与 NULL 相与恒为假，不加处理地查询**永远查不到**，
    会**静默**落回缺省且不报错（详见 `get_global_setting` 与 `is_ai_companion_enabled`）。
    """
    return _as_positive_int(
        get_global_setting(db, AI_COMPANION_PER_STUDENT_DAILY_LIMIT_KEY),
        settings.AI_COMPANION_DEFAULT_PER_STUDENT_DAILY_LIMIT,
    )
