"""AI 凭证的对称加密与掩码展示。

安全红线（docs/AI-GRADING-PRD.md §7.1 S1/S2）：

- ``api_key`` **加密后**才允许入库，明文不落库、不落日志、不落审计；
- 主密钥取自环境变量 ``AI_CREDENTIAL_KEY``，缺省时由 ``SECRET_KEY`` 派生 ——
  两者都不入库；``config.py`` 里的默认值仅为本地开发兜底；
- 对外接口只返回掩码（如 ``sk-****7f3a``），任何读接口都不回显明文。

派生方式：对主密钥做一次 SHA-256，得到 Fernet 要求的 32 字节 urlsafe-base64 key。
同一主密钥恒定派生出同一把密钥；主密钥轮换后旧密文将无法解密，
``decrypt_secret`` 此时返回空串（而非抛错），由调用方按「凭证不可用」降级。
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    """按当前主密钥构造 Fernet 实例。"""
    raw = (settings.AI_CREDENTIAL_KEY or settings.SECRET_KEY or "").strip()
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    """明文 → 密文（Fernet token，可安全入库）。空值原样返回空串。"""
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    """密文 → 明文。

    密文损坏或主密钥已轮换时返回空串，**不抛异常** —— 由调用方据此把凭证
    视为不可用并走降级路径，避免把解密失败暴露成 500。
    """
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""


def mask_secret(plain: str) -> str:
    """生成回显用掩码：保留前 3 位与后 4 位，中间固定 4 个星号。

    长度不足以区分时（≤10 位）整段打码，避免短密钥被掩码本身还原。
    """
    if not plain:
        return ""
    if len(plain) <= 10:
        return "*" * len(plain)
    return f"{plain[:3]}****{plain[-4:]}"
