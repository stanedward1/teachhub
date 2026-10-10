"""学校级 AI 能力配置读写工具（docs/DESIGN-AI校级能力.md §3 D1/D3）。

作用域约定
----------
`settings` 表以 `school_id` 区分作用域，本模块与 `platform_settings.py` 互补：

- 本模块只读写 **school 级行**（`school_id` = 具体学校 id），承载「校级 AI 能力」
  的 4 个配置（key 一律 `school_ai_` 前缀，见下方常量）；
- 平台级行（`school_id IS NULL`）归 `platform_settings.py`（该模块 docstring 明确
  承诺只管全局作用域），两模块互不越界。

为什么用独立 `school_ai_*` 前缀（而不是与平台 key 同名）
------------------------------------------------------
🔴 决定性理由是**权限旁路**：若校级行与平台 key 同名（如 `school_id=5` +
`ai_grading_enabled`），校内管理员可经既有通道 `PUT /api/settings/{key}`
（`routers/admin.py` → `admin_service.set_setting` 按 `user.school_id` 定位）直接
改写 —— 自行开关本校 AI、改本校额度，绕过「配置入口 = 超管专用端点」的需求约束。
配套防线（必做）：`admin_service.set_setting` 对 `school_` 前缀 key 返回 400
（写入黑名单），校内写入通道被堵死；校级覆盖只能经超管专用端点写入。

租户过滤语义（实测依据：设计文档 §2.7 探针 [A]/[B2]/[C]/[D]）
----------------------------------------------------------
- 读取用普通 `query().filter(Setting.school_id == school_id, Setting.key == key)`，
  **不加 `skip_tenant_filter`**：
  - 超管上下文（tenant scope=None，含 `_tenant_active=True` 形态）：ORM 事件在
    `school_id is None` 时直接 return（`app/tenant.py:88-89`），不注入过滤 ⇒ 查
    school 级行照常命中（探针 [A]）；
  - 本校上下文：ORM 注入的条件与本手写条件同值，无冲突（探针 [B]）。
  语义上校级配置**不是全局配置**，不应享受 skip 通道，避免滥用。
- **禁用 `db.get(Setting, id)`**：探针 [D] 证实 identity map 短路 —— 同 session
  已加载过该行时二次 `get` 零 SQL 返回缓存实体，配置变更可能读到陈旧值。
  统一走 `query().filter()`。
- ⚠️ 警示：当前设计不存在「租户上下文为校 A 却查校 B 配置」的调用方（校闸读取方
  的 school_id 恒等于请求租户，或调用方为超管）。若未来出现该场景，需重新评估
  skip_tenant_filter 的使用并补权限背书。

缺省语义（D3；与「缺省开」是同一哲学的两半：**未配置 = 跟随平台级**）
----------------------------------------------------------------
- 开关：无行 = **跟随平台闸**（等效开，前提平台闸已开）；行存在且为假值集
  （`0/false/no/off`，复用 `platform_settings._FALSY`）= **关**。即「关」必须
  **显式**落行，「开」是缺省。返回类型为 bool，不区分「未配置/显式开」。
- 额度上限：返回 `int | None`，**None = 不限（未配置校级池）**，与「配置了 0」
  严格区分：
  - 无行 / 空串 → None（不限，回归承诺：无校配置时校池判定恒为不限）；
  - `"0"` → 0（合法配置：今日 0 次，等效停用该池；与开关独立且冗余但无害）；
  - 正整数 → 该上限；
  - 非法（非数字 / 负数）→ None（fail-open：与「未配置」一致，配错不停摆，
    与 `platform_settings._as_positive_int`「非法回落缺省」精神一致，只是这里的
    缺省是 None）。
"""
from sqlalchemy.orm import Session

from app.models import Setting
from app.platform_settings import _FALSY

# ---------------- 校级 AI 能力配置键（school 级行，school_id = 具体学校） ----------------
# 本校 AI 批改开关（缺省开 = 跟随平台闸；显式假值 = 关）
SCHOOL_AI_GRADING_ENABLED_KEY = "school_ai_grading_enabled"
# 本校 AI 学伴开关（缺省开 = 跟随平台闸；显式假值 = 关）
SCHOOL_AI_COMPANION_ENABLED_KEY = "school_ai_companion_enabled"
# 本校批改每日调用次数上限（缺省不限 = None；显式 "0" = 上限 0）
SCHOOL_AI_GRADING_DAILY_LIMIT_KEY = "school_ai_grading_daily_limit"
# 本校学伴每日调用次数上限（缺省不限 = None；显式 "0" = 上限 0）
SCHOOL_AI_COMPANION_DAILY_LIMIT_KEY = "school_ai_companion_daily_limit"


def get_school_setting(
    db: Session, school_id: int, key: str, default: str | None = None
) -> str | None:
    """读取 school 级配置行（`school_id` = 具体学校，`uq_settings_school_key` 保证校内唯一）。

    Args:
        db: 数据库会话。
        school_id: 学校 id（**必须**为具体学校 id，全局行请走 `platform_settings.get_global_setting`）。
        key: 配置键。
        default: 配置行不存在时返回的默认值。

    Returns:
        配置的字符串值；不存在时返回 `default`。

    Note:
        普通 `query().filter()`，**不加 `skip_tenant_filter`、禁用 `db.get`**，
        实测依据见模块 docstring「租户过滤语义」一节。
    """
    row = (
        db.query(Setting)
        .filter(Setting.school_id == school_id, Setting.key == key)
        .first()
    )
    return row.value if row else default


def set_school_setting(
    db: Session, school_id: int, key: str, value: str | None
) -> Setting | None:
    """写入 / 清除 school 级配置行（超管专用端点使用，T04）。

    Args:
        db: 数据库会话。
        school_id: 学校 id。
        key: 配置键。
        value: 配置值（字符串）；**None ⇒ 删除该行 = 清除覆盖，恢复跟随缺省**
            （开关回到跟随平台闸、上限回到不限）。删行而非存 `"null"`/空串：
            `settings.value` 是 String(255)，存字符串会与「未配置」产生第三种歧义
            状态，且 `(school_id, key)` 唯一约束下删行干净可逆（再次写入即重建）。

    Returns:
        被写入的 `Setting` 实例；`value=None` 且行不存在时返回 None。

    Note:
        仅执行 `db.add` / 字段赋值 / `db.delete`，**不 commit**，由路由统一提交，
        保证「配置写入 + 审计日志」在同一事务内原子提交。
        新建行**显式赋 `school_id`**（铁律 #6）：超管上下文 `before_flush` 不回填
        也不篡改（探针 [C]）；校内租户上下文下 `before_flush` 只填空值，显式赋值
        同样保留。
    """
    row = (
        db.query(Setting)
        .filter(Setting.school_id == school_id, Setting.key == key)
        .first()
    )
    if value is None:
        if row:
            db.delete(row)
        return None
    if row:
        row.value = value
    else:
        # 显式赋 school_id（铁律 #6，勿依赖 before_flush 回填）
        row = Setting(school_id=school_id, key=key, value=value)
        db.add(row)
    return row


def _is_school_switch_on(value: str | None) -> bool:
    """校级开关解析（缺省**开**）：行不存在 / 值非假值集 ⇒ True；假值集 ⇒ False。

    「关」必须显式落行（值为 `0/false/no/off`，忽略大小写与首尾空白），
    其余任何取值（含未配置、非法串）都不构成「关」—— fail-open 与缺省开一致。
    """
    return (value or "").strip().lower() not in _FALSY


def is_school_ai_grading_enabled(db: Session, school_id: int | None) -> bool:
    """本校 AI 批改开关（缺省**开** = 跟随平台闸）。判定表见 `_is_school_switch_on`。"""
    if school_id is None:
        return True
    return _is_school_switch_on(
        get_school_setting(db, school_id, SCHOOL_AI_GRADING_ENABLED_KEY)
    )


def is_school_ai_companion_enabled(db: Session, school_id: int | None) -> bool:
    """本校 AI 学伴开关（缺省**开** = 跟随平台闸）。语义同 `is_school_ai_grading_enabled`。"""
    if school_id is None:
        return True
    return _is_school_switch_on(
        get_school_setting(db, school_id, SCHOOL_AI_COMPANION_ENABLED_KEY)
    )


def _as_school_limit(value: str | None) -> int | None:
    """校级每日上限解析（D3 判定表）：None/空串/非法/负值 ⇒ None（不限）；"0" ⇒ 0；正整数 ⇒ 原值。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = int(text)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def get_school_ai_daily_limit(db: Session, school_id: int | None) -> int | None:
    """本校批改每日调用次数上限；**None = 不限（未配置校级池）**。判定表见 `_as_school_limit`。"""
    if school_id is None:
        return None
    return _as_school_limit(
        get_school_setting(db, school_id, SCHOOL_AI_GRADING_DAILY_LIMIT_KEY)
    )


def get_school_companion_daily_limit(db: Session, school_id: int | None) -> int | None:
    """本校学伴每日调用次数上限；**None = 不限（未配置校级池）**。判定表同 `get_school_ai_daily_limit`。"""
    if school_id is None:
        return None
    return _as_school_limit(
        get_school_setting(db, school_id, SCHOOL_AI_COMPANION_DAILY_LIMIT_KEY)
    )
