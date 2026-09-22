"""系统管理接口（路由层：仅声明路径 / 依赖注入 / 参数解析 / 调用 service / 返回）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import (
    get_current_user,
    require_school_admin,
    require_super_admin,
    require_teacher,
)
from app.models import User
from app.schemas import AiCredentialSetting, AiGradingSetting, RegistrationSetting
from app.services import admin_service, ai_admin_service

router = APIRouter(prefix="/api", tags=["系统管理"])

# 账号管理 / 系统设置：仅学校管理员及以上（教师不可管理账号与全校设置）
admin_dep = require_school_admin

@router.get("/admin/users")
def list_users(role: str = "", keyword: str = "", _=Depends(admin_dep), db: Session = Depends(get_db)):
    return admin_service.list_users(db=db, role=role, keyword=keyword)


@router.post("/admin/users")
def create_user(payload: dict, user=Depends(admin_dep), db: Session = Depends(get_db)):
    return admin_service.create_user(db=db, payload=payload, user=user)


@router.put("/admin/users/{user_id}")
def update_user(user_id: int, payload: dict, user=Depends(admin_dep), db: Session = Depends(get_db)):
    return admin_service.update_user(db=db, user_id=user_id, payload=payload, user=user)


@router.put("/admin/users/{user_id}/password")
def reset_password(user_id: int, payload: dict, user=Depends(admin_dep), db: Session = Depends(get_db)):
    return admin_service.reset_password(db=db, user_id=user_id, payload=payload, user=user)


@router.delete("/admin/users/{user_id}")
def delete_user(user_id: int, user=Depends(admin_dep), db: Session = Depends(get_db)):
    return admin_service.delete_user(db=db, user_id=user_id, user=user)


@router.get("/settings")
def get_settings(_=Depends(admin_dep), db: Session = Depends(get_db)):
    return admin_service.get_settings(db=db)


@router.put("/settings/{key}")
def set_setting(key: str, payload: dict, user=Depends(admin_dep), db: Session = Depends(get_db)):
    return admin_service.set_setting(db=db, key=key, payload=payload, user=user)


@router.post("/settings/upgrade-grade")
def upgrade_grade(user=Depends(admin_dep), db: Session = Depends(get_db)):
    return admin_service.upgrade_grade(db=db, user=user)


@router.get("/admin/audit-logs/actions")
def list_audit_log_actions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return admin_service.list_audit_log_actions(db=db, user=user)


@router.get("/admin/audit-logs/stats")
def audit_log_stats(
    days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return admin_service.audit_log_stats(db=db, days=days, user=user)


@router.get("/admin/audit-logs")
def list_audit_logs(
    action: str = "",
    keyword: str = "",
    date: str = "",
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return admin_service.list_audit_logs(db=db, action=action, keyword=keyword, date=date, page=page, page_size=page_size, user=user)


@router.get("/stats/dashboard")
def dashboard(user=Depends(require_teacher), db: Session = Depends(get_db)):
    return admin_service.dashboard(db=db, user=user)


@router.get("/admin/platform/overview")
def platform_overview(user=Depends(require_super_admin), db: Session = Depends(get_db)):
    return admin_service.platform_overview(db=db, user=user)


@router.get("/admin/platform/registration")
def platform_registration(user=Depends(require_super_admin), db: Session = Depends(get_db)):
    return admin_service.platform_registration(db=db, user=user)


@router.put("/admin/platform/registration")
def set_platform_registration(
    payload: RegistrationSetting,
    user=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return admin_service.set_platform_registration(db=db, payload=payload, user=user)


# ---------------- AI 批改（平台超管专属） ----------------
# 凭证与批改开关**不得**复用 GET/PUT /api/settings：该接口挂在 admin_dep
# （= require_school_admin）下且明文返回全部配置行，凭证一旦入表每所学校的
# 管理员都能读到平台密钥（详见 docs/AI-GRADING-PRD.md §2.3）。
@router.get("/admin/platform/ai-credential")
def platform_ai_credential(user=Depends(require_super_admin), db: Session = Depends(get_db)):
    """读取 AI 服务凭证（**只返回掩码**，不含密钥明文）。"""
    return ai_admin_service.credential_view(db)


@router.put("/admin/platform/ai-credential")
def set_platform_ai_credential(
    payload: AiCredentialSetting,
    user=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """保存 AI 服务凭证（api_key 留空表示不修改；加密存储）。"""
    return ai_admin_service.set_credential(db=db, payload=payload, user=user)


@router.post("/admin/platform/ai-credential/test")
def test_platform_ai_credential(
    payload: AiCredentialSetting | None = None,
    user=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """连通性测试：可先用未保存的配置试连，api_key 留空则回退已存密钥。"""
    return ai_admin_service.test_credential(db=db, payload=payload, user=user)


@router.get("/admin/platform/ai-grading")
def platform_ai_grading(user=Depends(require_super_admin), db: Session = Depends(get_db)):
    """读取 AI 批改开关（总开关 / 自动入库 / 限额 / 当日用量）。"""
    return ai_admin_service.grading_setting(db)


@router.put("/admin/platform/ai-grading")
def set_platform_ai_grading(
    payload: AiGradingSetting,
    user=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """保存 AI 批改开关。总开关为平台级单一粒度（无按校开关）。"""
    return ai_admin_service.set_grading_setting(db=db, payload=payload, user=user)
