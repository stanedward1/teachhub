"""给 users.role 补建索引 ix_users_role

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-09-09 23:20:00

背景：User 模型的 role 字段声明了 index=True，但历史迁移未同步该索引，
导致数据库中 users 表缺少 ix_users_role。代码大量按 role 过滤
（User.role == 'student'、is_any_admin 等），缺失该索引会走全表扫描。
本迁移补建 ix_users_role。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 幂等：ix_users_role 可能已由更早的 f2c3d4e5a6b7（高频过滤字段索引）创建
    inspector = sa.inspect(op.get_bind())
    existing = {ix.get("name") for ix in inspector.get_indexes("users")}
    if "ix_users_role" not in existing:
        op.create_index('ix_users_role', 'users', ['role'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {ix.get("name") for ix in inspector.get_indexes("users")}
    if "ix_users_role" in existing:
        op.drop_index('ix_users_role', table_name='users')
