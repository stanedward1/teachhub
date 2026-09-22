import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_password_strength(password: str) -> str | None:
    """校验密码强度，返回错误信息；通过则返回 None。

    规则：至少 8 位，必须同时包含字母和数字，不能全为同一字符。
    """
    if len(password) < 8:
        return "密码长度至少 8 位"
    if not any(c.isalpha() for c in password):
        return "密码必须包含字母"
    if not any(c.isdigit() for c in password):
        return "密码必须包含数字"
    if len(set(password)) < 2:
        return "密码不能全为相同字符"
    return None


def create_access_token(
    subject: str,
    role: str,
    school_id: int | None = None,
    expires_delta: timedelta | None = None,
    token_version: int | None = None,
) -> str:
    """签发 JWT。payload 携带 school_id 作为租户上下文（super_admin 为 None）。

    `tv`（token_version）是**会话版本锚点**：access token 是无状态 JWT，无法逐个撤销，
    因此把用户当前的会话版本号写进声明，校验时比对（见 `app/deps.py::get_current_user`）。
    改密 / 重置密码只需把 `users.token_version` 加一，该用户此前签发的全部 access token
    立即失效 —— 这是「改密即踢出所有设备」得以成立的关键。
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": subject,
        "role": role,
        "school_id": school_id,
        "tv": int(token_version or 0),
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


# ---------------- 刷新令牌（F3） ----------------
def create_refresh_token() -> str:
    """生成一个高熵、URL 安全的刷新令牌明文（48 字节随机）。

    仅返回明文，落库前必须经 `hash_refresh_token` 摘要；明文只在签发响应中返回一次。
    """
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """计算刷新令牌的 sha256 十六进制摘要（64 字符），用于落库与按值检索。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
