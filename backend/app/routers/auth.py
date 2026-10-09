"""认证接口路由（B1 分层：仅做参数解析 / 依赖注入 / 调用 service / 返回）。

业务逻辑已下沉到 `app.services.auth_service`；本模块保留 router、limiter
（`main.py` 引用 `auth.limiter`，必须在此创建）与 `@limiter.limit` 装饰器
（slowapi 要求限流装饰器挂在路由函数上）。

对外 API 路径 / 字段名 / 状态码 / 中文文案保持不变，仅新增刷新令牌相关接口
（`POST /api/auth/refresh`、`POST /api/auth/logout`）与登录响应的
`refresh_token` 字段。
"""
from fastapi import APIRouter, Depends, File, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import School, User
from app.platform_settings import is_registration_allowed
from app.schemas import LoginRequest, PasswordRequest, RefreshRequest, RegisterRequest
from app.services import auth_service, uploads_service

router = APIRouter(prefix="/api/auth", tags=["认证"])

# 认证接口限流：按客户端 IP 维度限制请求频率。阈值集中配置在 `app/config.py`
# 的 `AUTH_*_RATE_LIMIT`（默认登录 30/min、注册 30/min、刷新 120/min、登出 60/min），
# 便于按部署规模调整而无需改代码。
# ⚠️ 阈值刻意**放得比较宽**：校园网 / 机房 / 企业出口是 NAT 共享 IP，几十上百人从同一
#    IP 登录会互相挤占配额；阈值过小会让后登录的人无辜收到 429「操作过于频繁」。
#    防爆破的主力是**账号维度**的失败锁定（5 次错口令锁 15 分钟），IP 限流只兜底
#    「同一出口高频轮询 / 分布式 IP 撞同一个账号」的场景。
# 注意：limiter 实例在 main.py 中创建并挂到 app.state，这里复用同一个实例
# （slowapi 要求所有路由共享同一个 Limiter 实例才能正确累计计数）。
def _client_key(request: Request) -> str:
    """限流键：默认取直连对端 IP；仅当显式开启 `TRUST_PROXY_HEADERS` 时才采信 XFF。

    `X-Forwarded-For` 是**客户端可伪造**的头，因此必须由配置显式打开（见 `config.py`），
    且取**最左**（最靠近真实客户端）的那个地址。不开启时直接用 `get_remote_address`
    —— 在反向代理后这会让所有请求共用代理 IP，此时应改为开启本开关，而不是无条件信任头。
    """
    if settings.TRUST_PROXY_HEADERS:
        first = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if first:
            return first
    return get_remote_address(request)


limiter = Limiter(key_func=_client_key)

# 兼容旧引用：`public_user` 已下沉到 service，这里保留别名指向同一实现。
public_user = auth_service.public_user


@router.post("/login")
@limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login(db, payload, user_agent=request.headers.get("user-agent"))


@router.post("/register")
@limiter.limit(settings.AUTH_REGISTER_RATE_LIMIT)
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    """学生自助注册（仅允许系统中尚不存在「班级+姓名」的学生）。

    注册即自动登录，与 `/login` 一致签发 access + refresh 令牌（见
    `auth_service._issue_session`）；`user_agent` 用于在刷新令牌上登记来源，便于审计。
    """
    return auth_service.register(db, payload, user_agent=request.headers.get("user-agent"))


@router.post("/refresh")
@limiter.limit(settings.AUTH_REFRESH_RATE_LIMIT)
def refresh(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)):
    """用刷新令牌换取新的令牌对（一次性轮换），无需鉴权。"""
    return auth_service.refresh(
        db, payload.refresh_token, user_agent=request.headers.get("user-agent")
    )


@router.post("/logout")
@limiter.limit(settings.AUTH_LOGOUT_RATE_LIMIT)
def logout(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)):
    """撤销刷新令牌（幂等），无需鉴权。

    与同组的 login / register / refresh 一致挂限流（阈值见 `app/config.py` 的
    `AUTH_*_RATE_LIMIT`）；登出是无成本可刷的端点（每次都按 token_hash 查一次库），
    但阈值远高于正常登出频率，不影响正常使用。"""
    return auth_service.logout(db, payload.refresh_token)


@router.get("/schools")
def public_schools(db: Session = Depends(get_db)):
    """登录页学校下拉（无需登录）：仅返回启用中的学校。"""
    rows = db.query(School).filter(School.status == "active").order_by(School.id).all()
    return {"items": [{"id": s.id, "name": s.name, "code": s.code} for s in rows]}


@router.get("/registration-status")
def registration_status(db: Session = Depends(get_db)):
    """学生登录页拉取注册开关（无需登录）。

    返回 `{"allow_registration": bool}`；缺省视为 True（向后兼容）。
    """
    return {"allow_registration": is_registration_allowed(db)}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"user": public_user(db, user)}


@router.put("/password")
def change_password(
    payload: PasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return auth_service.change_password(db, user, payload)


@router.post("/avatar")
def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """学生 / 教师上传自己的头像。

    校验（图片白名单 / 2MB 上限）、分块落盘与旧头像清理已下沉到
    :func:`app.services.uploads_service.save_avatar`；本路由仅做依赖注入、
    落库与返回（对外状态码 / 文案 / 返回结构保持不变）。
    """
    user.avatar = uploads_service.save_avatar(file, user_id=user.id, old_path=user.avatar)
    db.commit()
    return {"avatar": user.avatar}
