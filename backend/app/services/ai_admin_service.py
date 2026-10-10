"""AI 批改的平台管理服务：凭证与总开关（仅平台超管路径调用）。

对齐既有平台级配置范式（见 `services/admin_service.py::platform_registration`）：

- 写配置与 `audit()` **在同一事务内提交**，保证原子；
- 凭证密钥加密入库，读接口只回显掩码；
- 审计只记「改了哪些字段」，**绝不记密钥值**（安全红线 S2）。

凭证与开关都不受租户过滤影响（凭证表无 `school_id`；全局配置查询显式
`skip_tenant_filter`，见 `platform_settings` 模块说明）。
"""
import logging

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit import AUDIT_UPDATE_SCHOOL_AI_SETTINGS, audit
from app.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.models import (
    AiCredential,
    AiUsageDailyCompanionSchool,
    AiUsageDailySchool,
    School,
    User,
)
from app.platform_settings import (
    AI_AUTO_PUBLISH_EXCELLENT_KEY,
    AI_AUTO_PUBLISH_OWNER_KEY,
    AI_COMPANION_DAILY_LIMIT_KEY,
    AI_COMPANION_ENABLED_KEY,
    AI_COMPANION_PER_STUDENT_DAILY_LIMIT_KEY,
    AI_DAILY_LIMIT_KEY,
    AI_GRADING_ENABLED_KEY,
    AI_MAX_TOKENS_KEY,
    get_ai_companion_daily_limit,
    get_ai_companion_per_student_daily_limit,
    get_ai_daily_limit,
    get_ai_max_tokens,
    is_ai_auto_publish_enabled,
    is_ai_companion_enabled,
    is_ai_grading_enabled,
    set_global_setting,
)
from app.schemas import (
    AiCredentialSetting,
    AiCredentialTestSetting,
    AiGradingSetting,
    SchoolAiSetting,
)
from app.school_settings import (
    SCHOOL_AI_COMPANION_DAILY_LIMIT_KEY,
    SCHOOL_AI_COMPANION_ENABLED_KEY,
    SCHOOL_AI_GRADING_DAILY_LIMIT_KEY,
    SCHOOL_AI_GRADING_ENABLED_KEY,
    get_school_ai_daily_limit,
    get_school_companion_daily_limit,
    get_school_setting,
    is_school_ai_companion_enabled,
    is_school_ai_grading_enabled,
    set_school_setting,
)
from app.utils import stringify_dates
from app.services import ai_client, ai_grading

logger = logging.getLogger("teachhub.ai")


def default_vision_enabled(base_url: str | None, model: str | None) -> bool:
    """按「服务商与模型看起来是否支持视觉」给出 `vision_enabled` 的默认值。

    依据（DeepSeek 官方文档）：`deepseek-flash` 原生支持图片输入（仅
    JPEG/PNG/GIF/WebP，且图片只能放在 user 消息）。因此当 `base_url` 含
    "deepseek" 且 `model` 含 "flash" 或 "vision" 时默认开启，避免管理员忘勾
    开关而导致所有图片被静默跳过（上一轮"AI 看不懂小狗图片"的成因之一）。

    非 deepseek 服务商一律维持旧默认 `False`：我们无法核实其它服务商的视觉能力，
    且旧行为本就是 `False`，保持向后兼容、不替管理员做可能错误的猜测。
    """
    if not base_url or not model:
        return False
    bu = base_url.lower()
    m = model.lower()
    return "deepseek" in bu and ("flash" in m or "vision" in m)


def _credential(db: Session) -> AiCredential | None:
    """取平台唯一凭证行（无则 None）。

    凭证表**不含 `school_id` 列**，因此不受 ORM 租户过滤器影响，任何上下文下都能读到；
    访问控制由路由依赖 `require_super_admin` 负责。
    """
    return db.query(AiCredential).order_by(AiCredential.id.desc()).first()


def credential_view(db: Session) -> dict:
    """凭证的对外视图：**只含掩码**，不含任何明文密钥。"""
    cred = _credential(db)
    if cred is None:
        return {
            "configured": False,
            "provider": "deepseek",
            "base_url": "",
            "model": "",
            "api_key_masked": "",
            "vision_enabled": False,
            "enabled": False,
            "updated_at": None,
        }
    plain = decrypt_secret(cred.api_key_encrypted)
    return {
        "configured": bool(plain) and bool(cred.enabled),
        "provider": cred.provider,
        "base_url": cred.base_url,
        "model": cred.model,
        "api_key_masked": mask_secret(plain),
        "vision_enabled": bool(cred.vision_enabled),
        "enabled": bool(cred.enabled),
        "updated_at": cred.updated_at or cred.created_at,
    }


def set_credential(db: Session, payload: AiCredentialSetting, user: User) -> dict:
    """保存凭证（新建或更新）。

    `api_key` 为空视为「保持原密钥不变」；非空则加密后覆盖。
    """
    base_url = payload.base_url.strip()
    model = payload.model.strip()
    if not base_url or not model:
        raise HTTPException(status_code=400, detail="服务地址与模型名称不能为空")

    cred = _credential(db)
    created = cred is None
    if cred is None:
        cred = AiCredential(api_key_encrypted="", updated_by=user.id)
        db.add(cred)

    cred.provider = payload.provider.strip() or "deepseek"
    cred.base_url = base_url
    cred.model = model

    # vision_enabled 的赋值策略：
    # - 显式提供（payload.vision_enabled is not None）→ 以管理员选择为准；
    # - 新建且未提供 → 按服务商与模型智能推断默认（default_vision_enabled）；
    # - 更新且未提供 → 保持库里原值，绝不在管理员改别的字段时静默翻转他显式做过的选择。
    old_vision = None if created else bool(cred.vision_enabled)
    if payload.vision_enabled is not None:
        new_vision = bool(payload.vision_enabled)
    elif created:
        new_vision = default_vision_enabled(base_url, model)
    else:
        new_vision = old_vision  # 保持原值
    vision_changed = old_vision is not None and old_vision != new_vision
    cred.vision_enabled = new_vision

    cred.enabled = payload.enabled
    cred.updated_by = user.id

    changed = ["provider", "base_url", "model", "enabled"]
    if vision_changed:
        changed.append("vision_enabled")
    new_key = (payload.api_key or "").strip()
    if new_key:
        cred.api_key_encrypted = encrypt_secret(new_key)
        # 只记字段名，不记密钥值
        changed.append("api_key")

    audit(
        db,
        user,
        "set_ai_credential",
        target="ai_credential",
        detail=f"{'新建' if created else '更新'} 字段={changed}",
    )
    db.commit()
    db.refresh(cred)
    return credential_view(db)


def test_credential(
    db: Session, payload: AiCredentialTestSetting | None, user: User
) -> dict:
    """连通性测试（发一次最小请求）。

    两条路径：
    - 请求体带自定义 `base_url` + `model`（「先测后存」）→ 必须**同时自带**
      `api_key`；留空直接失败、绝不外呼（见下方安全说明）；
    - 请求体为空 / 字段缺省（`{}` / `null` / 无 body）→ 读已保存凭证来测试（正常路径）。

    🔴 `payload` 用**全可选**的 `AiCredentialTestSetting`：字段可能为 `None`，
    判定前必须 `(field or "").strip()`，否则空串/None 会触发 `AttributeError` → 500。
    **不回显密钥**。
    """
    if payload is not None and (payload.base_url or "").strip() and (payload.model or "").strip():
        base_url = payload.base_url.strip()
        model = payload.model.strip()
        api_key = (payload.api_key or "").strip()
        if not api_key:
            # 🔴 安全：禁止「自定义服务地址 + 复用已保存密钥」的组合 ——
            # 否则持超管 JWT 者可把库内明文密钥发往任意主机（密钥外泄 + SSRF）。
            # 自定义地址必须自带 API Key。
            return {
                "ok": False,
                "message": "填写了自定义服务地址时必须同时填写 API Key（不会把已保存的密钥发往自定义地址）",
                "elapsed_ms": None,
            }
    else:
        cred = _credential(db)
        if cred is None:
            return {"ok": False, "message": "尚未配置服务凭证", "elapsed_ms": None}
        base_url = cred.base_url
        model = cred.model
        api_key = decrypt_secret(cred.api_key_encrypted)

    if not api_key:
        return {"ok": False, "message": "尚未填写 API Key", "elapsed_ms": None}

    result = ai_client.test_connection(base_url=base_url, api_key=api_key, model=model)
    audit(
        db,
        user,
        "test_ai_credential",
        target="ai_credential",
        detail=f"连通性测试：{'成功' if result['ok'] else '失败'}",
    )
    db.commit()
    return result


def grading_setting(db: Session) -> dict:
    """AI 批改 / 学伴开关的对外视图（含当日用量，便于超管判断成本）。

    学伴（docs/DESIGN-AI学伴.md §13.1 DC-1）使用**独立**的成本刹车：
    `companion_enabled` / `companion_daily_limit` / `companion_today_call_count`
    与批改的同名字段互不影响、互不挤占 —— 超管需能分别看到两个计数（设计
    §13.7 对策①「可观测」）。
    """
    cred = _credential(db)
    configured = bool(cred) and bool(cred.enabled) and bool(decrypt_secret(cred.api_key_encrypted))
    # 延迟导入避免模块级循环依赖（ai_companion 会 import 本模块无关的 ai_grading）。
    from app.services import ai_companion

    return {
        "enabled": is_ai_grading_enabled(db),
        "auto_publish_excellent": is_ai_auto_publish_enabled(db),
        "daily_limit": get_ai_daily_limit(db),
        "max_tokens": get_ai_max_tokens(db),
        "companion_enabled": is_ai_companion_enabled(db),
        "companion_daily_limit": get_ai_companion_daily_limit(db),
        "companion_per_student_daily_limit": get_ai_companion_per_student_daily_limit(db),
        "companion_today_call_count": ai_companion.companion_today_call_count(db),
        "configured": configured,
        "today_call_count": ai_grading.today_call_count(db),
    }


def set_grading_setting(db: Session, payload: AiGradingSetting, user: User) -> dict:
    """保存总开关、自动入库开关与限额（写配置与审计同事务）。

    `set_global_setting` **只能在平台超管上下文调用**（超管 `school_id` 为 NULL，
    ORM 的 `before_flush` 不会改写新建行的 `school_id`）；本函数位于
    `require_super_admin` 之下，满足该前提（见 `platform_settings.set_global_setting`
    的 Warning）。学伴的 `companion_enabled` / `companion_daily_limit` 同为**平台级**
    全局配置（`school_id IS NULL`），校内上下文写入会被填成校内配置 ⇒ 非超管不可写。
    """
    set_global_setting(db, AI_GRADING_ENABLED_KEY, "1" if payload.enabled else "0")
    set_global_setting(
        db, AI_AUTO_PUBLISH_EXCELLENT_KEY, "1" if payload.auto_publish_excellent else "0"
    )
    set_global_setting(db, AI_DAILY_LIMIT_KEY, str(payload.daily_limit))
    set_global_setting(db, AI_MAX_TOKENS_KEY, str(payload.max_tokens))
    # AI 学伴（独立额度，见 docs/DESIGN-AI学伴.md §13）
    set_global_setting(
        db, AI_COMPANION_ENABLED_KEY, "1" if payload.companion_enabled else "0"
    )
    set_global_setting(
        db, AI_COMPANION_DAILY_LIMIT_KEY, str(payload.companion_daily_limit)
    )
    # 每个学生的每日次数上限（每生独立配额，docs/DESIGN-AI学伴配额.md D3）
    set_global_setting(
        db,
        AI_COMPANION_PER_STUDENT_DAILY_LIMIT_KEY,
        str(payload.companion_per_student_daily_limit),
    )

    # 记录「开启自动入库的人」：自动入库时计入 excellent_works.selected_by（NOT NULL）。
    # 记开启者而非执行者 —— 自动入库没有人工执行者，该配置即为其授权凭据。
    if payload.auto_publish_excellent:
        set_global_setting(db, AI_AUTO_PUBLISH_OWNER_KEY, str(user.id))

    audit(
        db,
        user,
        "set_ai_grading",
        target="ai_grading",
        detail=(
            f"enabled={payload.enabled} "
            f"auto_publish_excellent={payload.auto_publish_excellent} "
            f"daily_limit={payload.daily_limit} max_tokens={payload.max_tokens} "
            f"companion_enabled={payload.companion_enabled} "
            f"companion_daily_limit={payload.companion_daily_limit} "
            f"companion_per_student_daily_limit={payload.companion_per_student_daily_limit}"
        ),
    )
    db.commit()
    return grading_setting(db)


# ---------------- 校级 AI 能力配置（超管专用端点，docs/DESIGN-AI校级能力.md §3 D5 / T04） ----------------

# 池字段 → school 级配置键（开关字段单独映射，写入值为 "1"/"0"）
_SCHOOL_LIMIT_KEY_MAP = {
    "grading_daily_limit": SCHOOL_AI_GRADING_DAILY_LIMIT_KEY,
    "companion_daily_limit": SCHOOL_AI_COMPANION_DAILY_LIMIT_KEY,
}


def _ensure_super_admin(user: User) -> None:
    """service 层二次权限校验（路由装饰器 `require_super_admin` 已挡一道，纵深防御）。"""
    if user is None or user.role != "super_admin":
        raise HTTPException(status_code=403, detail="无权限访问该资源")


def _get_school(db: Session, school_id: int) -> School:
    """按 id 取学校，不存在 ⇒ 404「学校不存在」。

    用 `query().filter().first()` 而**非 `db.get`**：同 session 已加载过该行时
    `db.get` 会 identity map 短路返回缓存实体、零 SQL（设计 §2.7 探针 [D] 实测），
    可能掩盖「学校刚被删除」的事实。
    """
    school = db.query(School).filter(School.id == school_id).first()
    if school is None:
        raise HTTPException(status_code=404, detail="学校不存在")
    return school


def _school_ai_setting_view(db: Session, school: School) -> dict:
    """组装 GET/PUT 共用的合并视图（四段结构，docs/DESIGN-AI校级能力.md §3 D5）。

    - `platform`：平台当前值（开关 + 平台池上限）；
    - `school_override`：4 个 key 的**原始覆盖值**（字符串，无行 = null）；
    - `effective`：合并生效值（开关 = 平台 AND 学校；池 = 校级覆盖，null = 不限）；
    - `usage_today`：两校池今日 `call_count`（无行 = 0；日期取**数据库时钟**，
      与平台池 `_db_today` 同基准）。
    """
    sid = school.id
    platform = {
        "grading_enabled": is_ai_grading_enabled(db),
        "grading_daily_limit": get_ai_daily_limit(db),
        "companion_enabled": is_ai_companion_enabled(db),
        "companion_daily_limit": get_ai_companion_daily_limit(db),
    }
    override = {
        "grading_enabled": get_school_setting(db, sid, SCHOOL_AI_GRADING_ENABLED_KEY),
        "grading_daily_limit": get_school_setting(db, sid, SCHOOL_AI_GRADING_DAILY_LIMIT_KEY),
        "companion_enabled": get_school_setting(db, sid, SCHOOL_AI_COMPANION_ENABLED_KEY),
        "companion_daily_limit": get_school_setting(db, sid, SCHOOL_AI_COMPANION_DAILY_LIMIT_KEY),
    }
    effective = {
        "grading_enabled": platform["grading_enabled"] and is_school_ai_grading_enabled(db, sid),
        "grading_daily_limit": get_school_ai_daily_limit(db, sid),
        "companion_enabled": platform["companion_enabled"] and is_school_ai_companion_enabled(db, sid),
        "companion_daily_limit": get_school_companion_daily_limit(db, sid),
    }

    today = ai_grading._db_today(db)  # 数据库时钟（func.current_date()），与平台池同基准
    grading_row = (
        db.query(AiUsageDailySchool)
        .filter(AiUsageDailySchool.day == today, AiUsageDailySchool.school_id == sid)
        .first()
    )
    companion_row = (
        db.query(AiUsageDailyCompanionSchool)
        .filter(AiUsageDailyCompanionSchool.day == today, AiUsageDailyCompanionSchool.school_id == sid)
        .first()
    )
    usage_today = stringify_dates(
        {
            "day": today,
            # school_limit 回显校池上限（= effective 的池值，null = 不限）
            "grading": {"used": int(grading_row.call_count or 0) if grading_row else 0, "school_limit": effective["grading_daily_limit"]},
            "companion": {"used": int(companion_row.call_count or 0) if companion_row else 0, "school_limit": effective["companion_daily_limit"]},
        }
    )
    return {
        "school_id": sid,
        "school_name": school.name,
        "platform": platform,
        "school_override": override,
        "effective": effective,
        "usage_today": usage_today,
    }


def get_school_ai_setting(db: Session, school_id: int, user: User) -> dict:
    """读取校级 AI 能力配置合并视图（超管专用，docs/DESIGN-AI校级能力.md §3 D5）。"""
    _ensure_super_admin(user)
    school = _get_school(db, school_id)
    return _school_ai_setting_view(db, school)


def set_school_ai_setting(db: Session, school_id: int, payload: SchoolAiSetting, user: User) -> dict:
    """保存校级 AI 能力配置（部分更新三态，写库 + 审计同事务，返回合并视图）。

    三态判定（用 `payload.model_fields_set`，勿用 `if not payload.x`）：
    - 字段未传 → 不动；
    - 显式 null → `set_school_setting(..., None)` 删行 = 清除覆盖；
    - 开关显式 true/false → 写 `"1"`/`"0"`；
    - 池字段显式数值 → service 校验（**排除 bool** —— `bool` 是 `int` 子类；
      负数 ⇒ 400；`0` 合法）后写十进制字符串。

    校验**先于全部写入**：任一字段非法 ⇒ 400 且零落库副作用（get_db 关闭未提交
    事务，但先校验后写避免依赖该行为）。写入经 `set_school_setting`（T01 基建，
    新建行显式赋 school_id），本函数只 commit 一次，审计同事务原子。
    """
    _ensure_super_admin(user)
    school = _get_school(db, school_id)
    fields_set = payload.model_fields_set

    # 1) 先校验池字段（bool 排除 + 负数 400），非法即 400，零落库副作用
    limit_values: dict[str, int | None] = {}
    for field in _SCHOOL_LIMIT_KEY_MAP:
        if field not in fields_set:
            continue
        value = getattr(payload, field)
        if isinstance(value, bool):
            raise HTTPException(status_code=400, detail=f"{field} 不能是布尔值，请传非负整数")
        if value is not None and value < 0:
            raise HTTPException(status_code=400, detail=f"{field} 不能为负数")
        limit_values[field] = value

    # 2) 再统一写入（不 commit），并记录变更 key 列表
    changed: list[str] = []
    # 开关字段（grading_enabled / companion_enabled）仅 key 不同，走同一分支：
    # 显式 null ⇒ 删行（恢复跟随平台闸）；显式 true/false ⇒ 写 "1"/"0"。
    # 🔴 勿写 `"1" if value else "0"`：None 也是 falsy，会把显式 null 误写成 "0"。
    for field, key in (
        ("grading_enabled", SCHOOL_AI_GRADING_ENABLED_KEY),
        ("companion_enabled", SCHOOL_AI_COMPANION_ENABLED_KEY),
    ):
        if field in fields_set:
            value = getattr(payload, field)
            set_school_setting(
                db, school_id, key,
                None if value is None else ("1" if value else "0"),
            )
            changed.append(field)
    for field, key in _SCHOOL_LIMIT_KEY_MAP.items():
        if field in fields_set:
            value = limit_values[field]
            # 显式 null ⇒ 删行恢复跟随缺省（上限回到「不限」）
            set_school_setting(db, school_id, key, None if value is None else str(int(value)))
            changed.append(field)

    if changed:
        # 审计只记变更的 key 列表，**不记配置值**（detail 不写敏感值，T04 约定）
        audit(
            db,
            user,
            AUDIT_UPDATE_SCHOOL_AI_SETTINGS,
            target=f"学校#{school_id} ({school.name})",
            detail=f"变更字段={','.join(changed)}",
        )
    db.commit()
    return _school_ai_setting_view(db, school)
