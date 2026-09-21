"""drop last_login_at / last_login_ip from users

Revision ID: b0c1d2e3f4a5
Revises: b5c7d9e1f3a5
Create Date: 2026-09-10 15:35:00

「最后登录 IP」功能整体下线：线上为无 Docker / 无 nginx 的纯前端 + 后端形态，
客户端 IP 经 NAT 后本就不可见，且多层反代下无法稳定还原，故不再记录。
本迁移删除 `users.last_login_at` / `users.last_login_ip`。

**不删** `refresh_tokens.ip`：刷新令牌审计仍需要来源 IP，`_client_ip` 逻辑保留。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0c1d2e3f4a5'
down_revision: Union[str, Sequence[str], None] = 'b5c7d9e1f3a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除 users.last_login_at / users.last_login_ip。"""
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('last_login_ip')
        batch_op.drop_column('last_login_at')


def downgrade() -> None:
    """恢复两列（可空；不回溯历史数据，与新增时保持一致）。"""
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('last_login_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('last_login_ip', sa.String(45), nullable=True))
