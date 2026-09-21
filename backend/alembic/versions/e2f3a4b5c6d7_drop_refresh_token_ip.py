"""drop ip from refresh_tokens

Revision ID: e2f3a4b5c6d7
Revises: b0c1d2e3f4a5
Create Date: 2026-09-21 10:30:00

彻底下线客户端 IP 记录：本迁移删除 `refresh_tokens.ip` 列。

背景：`_client_ip` / `TRUSTED_PROXY_CIDRS` 等还原逻辑已在本轮删除，登录与刷新
都不再写入来源 IP，该列已无任何读写方（`app/services/auth_service.py` 的
`login` / `refresh` / `_new_refresh_token` 均已无 `ip` 参数），故一并删除。

⚠️ 本迁移会**丢弃该列的历史数据**，且 `downgrade()` 只能恢复空列、无法找回旧值。
本仓库上一次迁移 `b0c1d2e3f4a5` 的说明里写的「不删 refresh_tokens.ip」已被本条**取代**。

方言安全：`batch_alter_table` 包裹，MySQL（开发/生产）与 SQLite（测试）通用。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'b0c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除 refresh_tokens.ip。"""
    with op.batch_alter_table('refresh_tokens') as batch_op:
        batch_op.drop_column('ip')


def downgrade() -> None:
    """恢复可空的 ip 列（不回溯历史数据）。"""
    with op.batch_alter_table('refresh_tokens') as batch_op:
        batch_op.add_column(sa.Column('ip', sa.String(64), nullable=True))
