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
) -> str:
    """签发 JWT。payload 携带 school_id 作为租户上下文（super_admin 为 None）。"""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "role": role, "school_id": school_id, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
