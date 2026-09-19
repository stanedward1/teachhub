"""add refresh_tokens table

Revision ID: c4d5e6f7a8b9
Revises: b3c2d1e0f9a8
Create Date: 2026-09-11 10:00:00

F3：新增 refresh_tokens 表，支撑 access token 过期后静默刷新（含一次性轮换）。

- token_hash 存 sha256 十六进制摘要（唯一索引），明文仅在签发时返回一次；
- user_id 级联删除（父账号删除时令牌一并清理）；
- school_id 置空删除（学校删除后令牌保留但失去租户归属，平台超管为 NULL）；
- revoked_at / replaced_by 支持轮换与登出失效。

方言安全：仅使用 create_table + create_index，SQLite（测试）与 MySQL（开发/生产）通用。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3c2d1e0f9a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """建 refresh_tokens 表与索引。"""
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('school_id', sa.Integer(), nullable=True),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('replaced_by', sa.String(length=64), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('ip', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False
    )
    op.create_index(
        op.f('ix_refresh_tokens_school_id'), 'refresh_tokens', ['school_id'], unique=False
    )
    op.create_index(
        op.f('ix_refresh_tokens_token_hash'),
        'refresh_tokens',
        ['token_hash'],
        unique=True,
    )
    op.create_index(
        op.f('ix_refresh_tokens_expires_at'),
        'refresh_tokens',
        ['expires_at'],
        unique=False,
    )


def downgrade() -> None:
    """对称删除索引与表。"""
    op.drop_index(op.f('ix_refresh_tokens_expires_at'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_token_hash'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_school_id'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_user_id'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
