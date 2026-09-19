from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class RefreshToken(Base):
    """刷新令牌（F3）：access token 过期后静默换取新令牌对，并做一次性轮换。

    设计要点：

    - **只存摘要**：`token_hash` 保存明文的 sha256 十六进制摘要，明文仅在签发时返回一次。
    - **租户归属**：`school_id` 记录令牌所属学校（平台超管为 NULL）。该列会被
      `app/tenant.py` 的 ORM 事件纳入自动租户过滤，因此登录 / 刷新时**显式**写入，
      不依赖自动回填。
    - **轮换与撤销**：`revoked_at` 标记失效时间，`replaced_by` 记录轮换后的新令牌摘要，
      形成可追溯的令牌链；`logout` 与刷新轮换都通过置 `revoked_at` 失效旧令牌。
    """

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 租户归属（平台超管为 NULL）；登录/刷新时显式写入
    school_id = Column(
        Integer,
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # sha256 十六进制摘要（64 字符），唯一
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True)
    replaced_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    user_agent = Column(String(255), nullable=True)
    ip = Column(String(64), nullable=True)
