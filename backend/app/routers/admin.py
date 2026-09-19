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
from app.schemas import RegistrationSetting
from app.services import admin_service

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
