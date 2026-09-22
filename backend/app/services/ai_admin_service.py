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

from app.audit import audit
from app.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.models import AiCredential, User
from app.platform_settings import (
    AI_AUTO_PUBLISH_EXCELLENT_KEY,
    AI_AUTO_PUBLISH_OWNER_KEY,
    AI_DAILY_LIMIT_KEY,
    AI_GRADING_ENABLED_KEY,
    AI_MAX_TOKENS_KEY,
    get_ai_daily_limit,
    get_ai_max_tokens,
    is_ai_auto_publish_enabled,
    is_ai_grading_enabled,
    set_global_setting,
)
from app.schemas import AiCredentialSetting, AiGradingSetting
from app.services import ai_client, ai_grading

logger = logging.getLogger("teachhub.ai")


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
    cred.vision_enabled = payload.vision_enabled
    cred.enabled = payload.enabled
    cred.updated_by = user.id

    changed = ["provider", "base_url", "model", "vision_enabled", "enabled"]
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


def test_credential(db: Session, payload: AiCredentialSetting | None, user: User) -> dict:
    """连通性测试（发一次最小请求）。

    优先使用请求体里**尚未保存**的配置，便于超管「先测后存」；
    请求体的 `api_key` 留空时回退到已存密钥。**不回显密钥**。
    """
    if payload is not None and payload.base_url.strip() and payload.model.strip():
        base_url = payload.base_url.strip()
        model = payload.model.strip()
        api_key = (payload.api_key or "").strip()
        if not api_key:
            cred = _credential(db)
            api_key = decrypt_secret(cred.api_key_encrypted) if cred else ""
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
    """AI 批改开关的对外视图（含当日用量，便于超管判断成本）。"""
    cred = _credential(db)
    configured = bool(cred) and bool(cred.enabled) and bool(decrypt_secret(cred.api_key_encrypted))
    return {
        "enabled": is_ai_grading_enabled(db),
        "auto_publish_excellent": is_ai_auto_publish_enabled(db),
        "daily_limit": get_ai_daily_limit(db),
        "max_tokens": get_ai_max_tokens(db),
        "configured": configured,
        "today_call_count": ai_grading.today_call_count(db),
    }


def set_grading_setting(db: Session, payload: AiGradingSetting, user: User) -> dict:
    """保存总开关、自动入库开关与限额（写配置与审计同事务）。"""
    set_global_setting(db, AI_GRADING_ENABLED_KEY, "1" if payload.enabled else "0")
    set_global_setting(
        db, AI_AUTO_PUBLISH_EXCELLENT_KEY, "1" if payload.auto_publish_excellent else "0"
    )
    set_global_setting(db, AI_DAILY_LIMIT_KEY, str(payload.daily_limit))
    set_global_setting(db, AI_MAX_TOKENS_KEY, str(payload.max_tokens))

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
            f"daily_limit={payload.daily_limit} max_tokens={payload.max_tokens}"
        ),
    )
    db.commit()
    return grading_setting(db)
