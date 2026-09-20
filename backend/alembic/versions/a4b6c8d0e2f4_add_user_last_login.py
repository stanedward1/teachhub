"""add last_login_at / last_login_ip to users

Revision ID: a4b6c8d0e2f4
Revises: a7b8c9d0e1f2
Create Date: 2026-09-20 18:30:00

学生管理处需要展示「最后一次登录的 IP」，故在 users 上记录最后登录时间与来源 IP。
两列均可空：存量账号无历史数据，登录一次后自动填充。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4b6c8d0e2f4'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增 users.last_login_at / users.last_login_ip。"""
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('last_login_at', sa.DateTime(), nullable=True))
        # 45 字符可容纳 IPv6 完整写法（含 IPv4-mapped 形式）
        batch_op.add_column(sa.Column('last_login_ip', sa.String(45), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('last_login_ip')
        batch_op.drop_column('last_login_at')
