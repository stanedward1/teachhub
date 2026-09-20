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
limiter = Limiter(key_func=get_remote_address)

# 兼容旧引用：`public_user` 已下沉到 service，这里保留别名指向同一实现。
public_user = auth_service.public_user


def _client_ip(request: Request) -> str | None:
    """还原真实客户端 IP。

    部署在 nginx 之后时 `request.client.host` 只会拿到 nginx 自身地址（127.0.0.1），
    因此优先读反向代理头：

    - `X-Real-IP`：nginx `proxy_set_header X-Real-IP $remote_addr`，最可靠；
    - `X-Forwarded-For`：形如 `client, proxy1, proxy2`，取**最右侧**一跳 ——
      nginx 用 `$proxy_add_x_forwarded_for` 时会把真实对端追加在末尾，
      而左侧内容可被客户端伪造，取最右可避免完全采信伪造值。

    **前提**：服务确实位于可信反向代理之后。若直连暴露且未过滤该头，
    客户端可伪造 IP —— 此时该值仅作参考，不作为安全依据。
    """
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # 最右侧一跳：代理链中由最近的代理写入，比最左侧更可信
        hops = [h.strip() for h in xff.split(",") if h.strip()]
        if hops:
            return hops[-1]
    client = request.client
    return client.host if client else None


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    """从请求中提取客户端 UA 与 IP，用于记录刷新令牌来源与最后登录留痕。"""
    return request.headers.get("user-agent"), _client_ip(request)


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user_agent, ip = _client_meta(request)
    return auth_service.login(db, payload, user_agent=user_agent, ip=ip)


@router.post("/register")
@limiter.limit("10/minute")
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    """学生自助注册（仅允许系统中尚不存在「班级+姓名」的学生）。"""
    return auth_service.register(db, payload)


@router.post("/refresh")
@limiter.limit("30/minute")
def refresh(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)):
    """用刷新令牌换取新的令牌对（一次性轮换），无需鉴权。"""
    user_agent, ip = _client_meta(request)
    return auth_service.refresh(db, payload.refresh_token, user_agent=user_agent, ip=ip)


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
