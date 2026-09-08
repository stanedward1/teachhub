"""add assignment attachments table

Revision ID: b6d5e4f3a2c1
Revises: a1b2c3d4e5f6
Create Date: 2026-09-07 22:45:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b6d5e4f3a2c1'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """建 assignment_attachments 子表（教师布置任务上传多附件，一对多）。"""
    op.create_table(
        'assignment_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('filepath', sa.String(500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assignment_attachments_id'), 'assignment_attachments', ['id'], unique=False)
    op.create_index(op.f('ix_assignment_attachments_assignment_id'), 'assignment_attachments', ['assignment_id'], unique=False)


def downgrade() -> None:
    # 直接 drop_table 连带删除索引与外键（避免 MySQL 下 drop_index 报 1553）
    op.drop_table('assignment_attachments')
