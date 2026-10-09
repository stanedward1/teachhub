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
from app.schemas import (
    AiCredentialSetting,
    AiCredentialTestSetting,
    AiGradingSetting,
    RegistrationSetting,
    SchoolAiSetting,
    StudentDeviceSetting,
)
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
def get_settings(user=Depends(admin_dep), db: Session = Depends(get_db)):
    return admin_service.get_settings(db=db, user=user)


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


@router.get("/admin/platform/student-device")
def platform_student_device(user=Depends(require_super_admin), db: Session = Depends(get_db)):
    """读取「学生单设备在线」开关（平台级，缺省开启）。"""
    return admin_service.platform_student_device(db=db, user=user)


@router.put("/admin/platform/student-device")
def set_platform_student_device(
    payload: StudentDeviceSetting,
    user=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """开启/关闭「学生单设备在线」：开启后学生登录会把先登录的设备挤下线。"""
    return admin_service.set_platform_student_device(db=db, payload=payload, user=user)


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
    # 🔴 用**全可选**的 `AiCredentialTestSetting`：`{}` / `null` / 缺 body 都必须 200
    # （回退已保存凭证）。保存用的 `AiCredentialSetting` 必填校验不受影响（PUT 仍 422）。
    payload: AiCredentialTestSetting | None = None,
    user=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """连通性测试：可先用未保存的配置试连（自定义地址须自带 API Key）；
    请求体留空时测试已保存的配置。"""
    return ai_admin_service.test_credential(db=db, payload=payload, user=user)


@router.get("/admin/platform/ai-grading")
def platform_ai_grading(user=Depends(require_super_admin), db: Session = Depends(get_db)):
    """读取 AI 批改 / 学伴开关（总开关 / 自动入库 / 限额 / 当日用量）。

    含 **AI 学伴**（docs/DESIGN-AI学伴.md）的 `companion_enabled` /
    `companion_daily_limit` / `companion_today_call_count` —— 学伴使用**独立**的成本
    刹车（独立计数表），与批改额度互不挤占，故两个当日计数分别返回。
    """
    return ai_admin_service.grading_setting(db)


@router.put("/admin/platform/ai-grading")
def set_platform_ai_grading(
    payload: AiGradingSetting,
    user=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """保存 AI 批改 / 学伴开关。总开关为平台级单一粒度（无按校开关）。

    平台级设置（`school_id IS NULL`）**只能在超管路径写入**；校内上下文（校管）调用
    会被 `require_super_admin` 拦下（403），不会把全局配置误写成校内配置。
    """
    return ai_admin_service.set_grading_setting(db=db, payload=payload, user=user)


# ---------------- 校级 AI 能力配置（平台超管专属，docs/DESIGN-AI校级能力.md §3 D5 / T04） ----------------
# 路由归属 admin.py（平台管理类端点集中于此）；students.py 的学校 CRUD 是历史原因，不跟。
@router.get("/admin/schools/{school_id}/ai-settings")
def school_ai_settings(
    school_id: int,
    user=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """读取校级 AI 能力配置合并视图（platform / school_override / effective / usage_today）。"""
    return ai_admin_service.get_school_ai_setting(db=db, school_id=school_id, user=user)


@router.put("/admin/schools/{school_id}/ai-settings")
def set_school_ai_settings(
    school_id: int,
    payload: SchoolAiSetting,
    user=Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """保存校级 AI 能力配置（部分更新三态：未传=不动 / 显式 null=清除覆盖 / 值=写入）。"""
    return ai_admin_service.set_school_ai_setting(db=db, school_id=school_id, payload=payload, user=user)
