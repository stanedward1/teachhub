"""认证接口路由（B1 分层：仅做参数解析 / 依赖注入 / 调用 service / 返回）。

业务逻辑已下沉到 `app.services.auth_service`；本模块保留 router、limiter
（`main.py` 引用 `auth.limiter`，必须在此创建）与 `@limiter.limit` 装饰器
（slowapi 要求限流装饰器挂在路由函数上）。

对外 API 路径 / 字段名 / 状态码 / 中文文案保持不变，仅新增刷新令牌相关接口
（`POST /api/auth/refresh`、`POST /api/auth/logout`）与登录响应的
`refresh_token` 字段。
"""
import ipaddress
import logging
import os
import uuid
from functools import lru_cache

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

logger = logging.getLogger(__name__)

# 登录接口限流：按客户端 IP 维度限制登录尝试频率，配合应用层的账号锁定策略，
# 防止攻击者绕过账号锁定、用分布式 IP 对同一账号进行暴力破解。
# 注意：limiter 实例在 main.py 中创建并挂到 app.state，这里复用同一个实例
# （slowapi 要求所有路由共享同一个 Limiter 实例才能正确累计计数）。
limiter = Limiter(key_func=get_remote_address)

# 兼容旧引用：`public_user` 已下沉到 service，这里保留别名指向同一实现。
public_user = auth_service.public_user


def _normalize_hop(value: str) -> str:
    """去掉 IPv4:端口 / [IPv6]:端口 里的端口部分，只留地址。"""
    value = value.strip()
    if value.startswith("["):  # [2001:db8::1]:1234
        return value[1:].split("]", 1)[0]
    if value.count(":") == 1:  # 114.114.114.114:1234
        return value.split(":", 1)[0]
    return value


def _parse_ip(value: str) -> ipaddress._BaseAddress | None:
    """把一跳解析成 IP 对象；不是合法 IP（如 XFF 里的 `unknown` 占位符）则返回 None。

    返回对象而非字符串，顺带完成规范化（`::1`、`114.114.114.114` 都是标准写法）。
    """
    try:
        return ipaddress.ip_address(_normalize_hop(value))
    except ValueError:
        return None


def _is_own_hop(ip: ipaddress._BaseAddress) -> bool:
    """该跳是否**确定属于我们自己的基础设施**（因而不可能是客户端）。

    默认只判定三类地址：**回环 / 链路本地 / 未指定** —— 它们在任何拓扑下都
    "不可能是真实客户端"，是唯一可以无条件丢弃的判据。额外网段由
    `settings.TRUSTED_PROXY_CIDRS` 提供（默认空）。

    **为什么不能把所有内网段（RFC1918）都当成自有**：真实客户端本身常常就在内网
    （校园网 `192.168.x`、`10.x`）。若把内网一并丢弃，就会丢掉**不可伪造**的
    `X-Real-IP` 转而信任**可被客户端伪造**的 `X-Forwarded-For` —— 这是实测踩过的坑
    （`X-Real-IP=192.168.1.100` + `XFF=1.2.3.4,192.168.1.100` 会返回伪造的 `1.2.3.4`）。

    多层反代时内层 nginx 的 `$remote_addr` 通常是 `127.0.0.1` 或 docker 网关地址，
    因此「回环」这一条就足以识别绝大多数自有跳；docker 网关那种情况由 nginx 的
    realip 模块先还原（见 `frontend/nginx.conf`），或由 `TRUSTED_PROXY_CIDRS` 兜底。
    """
    if ip.is_loopback or ip.is_link_local or ip.is_unspecified:
        return True
    for net in _own_proxy_networks():
        if net.version == ip.version and ip in net:
            return True
    return False


@lru_cache(maxsize=1)
def _own_proxy_networks() -> tuple[ipaddress._BaseNetwork, ...]:
    """解析 `settings.TRUSTED_PROXY_CIDRS` 为网段元组（解析失败的条目跳过并告警）。"""
    nets: list[ipaddress._BaseNetwork] = []
    for raw in settings.TRUSTED_PROXY_CIDRS:
        try:
            nets.append(ipaddress.ip_network(raw, strict=False))
        except ValueError:
            logger.warning("TRUSTED_PROXY_CIDRS 含非法网段，已忽略: %r", raw)
    return tuple(nets)


def _client_ip(request: Request) -> str | None:
    """还原真实客户端 IP，支持**多层**反向代理。

    部署在反向代理之后时 `request.client.host` 只会拿到直连对端（代理自身），
    因此需要从代理头里还原：

    - `X-Real-IP`：由**最近一跳**代理写入（nginx `proxy_set_header X-Real-IP $remote_addr`）。
      因为它来自我们自己的直连代理，客户端无法伪造，**可信度最高**。
    - `X-Forwarded-For`：形如 `client, proxy1, proxy2`，**越靠左越接近原始客户端**；
      每经过一层代理，该层会把自己的对端地址追加到**末尾**。

    还原策略（按优先级）：

    1. `X-Real-IP` 存在且**不是我们自己的代理**（回环 / 链路本地 / 未指定，或命中
       `TRUSTED_PROXY_CIDRS`）→ 直接采用。它由直连代理写入、**客户端无法伪造**，
       因此即使值是内网地址（校园网客户端）也应当采用。
    2. 否则（缺失，或已被自有代理地址覆盖）→ 退回 `X-Forwarded-For`，取**最左的非自有跳**。
    3. 都没有 → 回退到 TCP 对端。

    为什么不能简单地"取最右一跳"：**多层代理**时内层 nginx 的 `$remote_addr` 是上一跳
    （通常是 `127.0.0.1`），它会被追加到 XFF 末尾，于是"最右"永远是我们的基础设施地址 ——
    这正是「所有用户都记成 127.0.0.1」的成因。

    为什么"自有代理"只按回环 / 链路本地判定、**不按 RFC1918 内网段**：真实客户端本身
    常常就在内网（校园网 `192.168.x`）。把内网一律当自有，会丢掉**不可伪造**的
    `X-Real-IP`，转而信任**可被客户端伪造**的 XFF —— 实测踩过这个坑。
    若内层代理以别的地址连入（如 docker 网关 `172.17.0.1`），用 `TRUSTED_PROXY_CIDRS` 声明。

    **前提与边界**：服务应位于可信反向代理之后。走路径 1 时该值不可伪造；只有在
    `X-Real-IP` 被自有代理地址覆盖、不得不依据 XFF 判断时，才可能被客户端自带的 XFF 伪造
    —— 故该值仅供**展示与留痕**，**不得作为安全依据**（登录限流走 TCP 对端，不受影响）。
    """
    real_ip = _parse_ip(request.headers.get("x-real-ip") or "")

    # 1) 直连代理写下的 X-Real-IP：客户端无法伪造，最可信。
    #    仅当它是我们自己的代理地址时才丢弃 —— 多层代理时内层 nginx 会把
    #    $remote_addr（通常 127.0.0.1）写进来，那种值必须丢弃。
    if real_ip is not None and not _is_own_hop(real_ip):
        return str(real_ip)

    # 2) X-Real-IP 缺失或已被自有代理地址覆盖：退回 X-Forwarded-For 链。
    #    取最左的非自有跳（最接近原始客户端），跳过自有跳以免取到 127.0.0.1。
    xff = request.headers.get("x-forwarded-for")
    hops = []
    for raw in xff.split(",") if xff else []:
        ip = _parse_ip(raw)
        if ip is not None:  # 跳过 "unknown" 之类的非 IP 占位符
            hops.append(ip)
    for ip in hops:
        if not _is_own_hop(ip):
            return str(ip)
    # 整条链都是自有/保留地址（本机访问、链路本地等）：取最左一跳已是最接近客户端的答案
    if hops:
        return str(hops[0])

    # 3) 完全没有任何来源：如实返回 X-Real-IP，或回退到 TCP 对端（直连时即真实 IP）
    if real_ip is not None:
        return str(real_ip)
    client = request.client
    return client.host if client else None


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    """从请求中提取客户端 UA 与 IP，用于记录刷新令牌来源与最后登录留痕。"""
    return request.headers.get("user-agent"), _client_ip(request)


def _log_client_ip(ip: str | None, request: Request) -> None:
    """打印一行 IP 还原诊断；结果不可信（仍为回环）时**再给一条可操作告警**。

    排查「所有用户都记成同一个 IP」时，INFO 那行可直接看出是链路根本没传代理头，
    还是被某一层代理覆盖成了 `127.0.0.1`（还原算法见 `_client_ip`）。

    额外的 WARNING 是有意为之：线上「**所有**用户都还原成 `127.0.0.1`」几乎总不是本机访问，
    而是**反向代理没转发 `X-Real-IP` / `X-Forwarded-For`**。这类问题在日志里极易被忽略，
    所以这里直接把「该去改哪一行配置」喊出来，省掉一轮排查。（本地开发 / SSH 隧道访问时
    也会命中此告警，属预期噪音。）
    """
    peer = request.client.host if request.client else None
    real_ip = request.headers.get("x-real-ip")
    xff = request.headers.get("x-forwarded-for")
    logger.info(
        "客户端 IP 还原: ip=%s | 直连对端=%s | X-Real-IP=%r | X-Forwarded-For=%r",
        ip, peer, real_ip, xff,
    )

    parsed = _parse_ip(ip) if ip else None
    if parsed is not None and parsed.is_loopback:
        logger.warning(
            "客户端 IP 还原结果仍为回环地址 %s —— 线上若**所有**用户都是它，几乎总是因为"
            "反向代理未转发客户端 IP：请检查 nginx `location /api` 里的 "
            "`proxy_set_header X-Real-IP $remote_addr;` 与 "
            "`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`（见 README §6）。"
            "若确实是从本机 / SSH 隧道访问，则可忽略本条。"
            "本次原始头：X-Real-IP=%r | X-Forwarded-For=%r | 直连对端=%s",
            ip, real_ip, xff, peer,
        )


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user_agent, ip = _client_meta(request)
    _log_client_ip(ip, request)
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
