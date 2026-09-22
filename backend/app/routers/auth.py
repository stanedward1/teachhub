"""认证接口路由（B1 分层：仅做参数解析 / 依赖注入 / 调用 service / 返回）。

业务逻辑已下沉到 `app.services.auth_service`；本模块保留 router、limiter
（`main.py` 引用 `auth.limiter`，必须在此创建）与 `@limiter.limit` 装饰器
（slowapi 要求限流装饰器挂在路由函数上）。

对外 API 路径 / 字段名 / 状态码 / 中文文案保持不变，仅新增刷新令牌相关接口
（`POST /api/auth/refresh`、`POST /api/auth/logout`）与登录响应的
`refresh_token` 字段。
"""
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import School, User
from app.platform_settings import is_registration_allowed
from app.schemas import LoginRequest, PasswordRequest, RefreshRequest, RegisterRequest
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["认证"])

# 登录接口限流：按客户端 IP 维度限制登录尝试频率，配合应用层的账号锁定策略，
# 防止攻击者绕过账号锁定、用分布式 IP 对同一账号进行暴力破解。
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
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login(db, payload, user_agent=request.headers.get("user-agent"))


@router.post("/register")
@limiter.limit("10/minute")
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    """学生自助注册（仅允许系统中尚不存在「班级+姓名」的学生）。"""
    return auth_service.register(db, payload)


@router.post("/refresh")
@limiter.limit("30/minute")
def refresh(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)):
    """用刷新令牌换取新的令牌对（一次性轮换），无需鉴权。"""
    return auth_service.refresh(
        db, payload.refresh_token, user_agent=request.headers.get("user-agent")
    )


@router.post("/logout")
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    """撤销刷新令牌（幂等），无需鉴权。"""
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


_AVATAR_DIR = settings.AVATAR_DIR
_AVATAR_MAX_SIZE = 2 * 1024 * 1024  # 2MB
_AVATAR_ALLOWED = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


@router.post("/avatar")
def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """学生 / 教师上传自己的头像。"""
    original = file.filename or "avatar"
    ext = os.path.splitext(original)[1].lower()
    if ext not in _AVATAR_ALLOWED:
        raise HTTPException(status_code=400, detail=f"仅支持图片格式：{'、'.join(sorted(_AVATAR_ALLOWED))}")

    name = f"avatar_{user.id}_{uuid.uuid4().hex[:8]}{ext}"
    os.makedirs(_AVATAR_DIR, exist_ok=True)
    dest = os.path.join(_AVATAR_DIR, name)

    size = 0
    chunk_size = 1024 * 1024
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = file.file.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > _AVATAR_MAX_SIZE:
                    f.close()
                    os.remove(dest)
                    raise HTTPException(status_code=413, detail=f"头像文件不能超过 {_AVATAR_MAX_SIZE // (1024*1024)}MB")
                f.write(chunk)
    except HTTPException:
        raise
    except Exception:
        if os.path.exists(dest):
            os.remove(dest)
        raise

    # 删除旧头像文件
    if user.avatar:
        old_name = user.avatar.rsplit("/", 1)[-1]
        old_full = os.path.join(_AVATAR_DIR, old_name)
        if os.path.exists(old_full):
            os.remove(old_full)

    user.avatar = f"/uploads/avatars/{name}"
    db.commit()
    return {"avatar": user.avatar}
