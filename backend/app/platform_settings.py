"""平台级全局配置读写工具。

作用域约定
----------
`settings` 表以 `school_id` 区分作用域：

- `school_id` 为具体学校 id → **校内配置**（校内 key 唯一，见 `uq_settings_school_key`）；
- `school_id IS NULL` → **平台级全局配置**（跨校生效，由平台超管维护）。

本模块只读写全局作用域（`school_id IS NULL`）的配置行，供认证模块（学生注册开关）
与平台超管接口复用；校内配置请勿使用本模块（校内配置由 `routers/admin.set_setting`
以 `user.school_id` 定位）。

默认值策略
----------
读取缺失的配置项时返回调用方传入的 `default`（而非抛错），保证「配置行不存在」与
「配置项从未被设置过」两种情形下行为可预期。学生自助注册开关 `allow_registration`
在缺省时视为 **True**，以保持引入开关之前的历史行为（默认开放注册），实现向后兼容。
"""
from sqlalchemy.orm import Session

from app.models import Setting

# 学生自助注册总开关的全局配置键（school_id IS NULL）
ALLOW_REGISTRATION_KEY = "allow_registration"

# 视为「真」的字符串取值（比较前忽略大小写并去除首尾空白）
_TRUTHY = {"1", "true", "yes", "on"}


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
    """
    row = (
        db.query(Setting)
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
