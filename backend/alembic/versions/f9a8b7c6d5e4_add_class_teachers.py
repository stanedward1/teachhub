"""add class_teachers table (multiple teachers per class)

Revision ID: f9a8b7c6d5e4
Revises: e7f6a5b4c3d2
Create Date: 2026-08-26 19:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9a8b7c6d5e4'
down_revision: Union[str, Sequence[str], None] = 'e7f6a5b4c3d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('class_teachers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('class_id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['class_id'], ['classrooms.id'], ),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('class_id', 'teacher_id', name='uq_class_teacher')
    )
    op.create_index(op.f('ix_class_teachers_id'), 'class_teachers', ['id'], unique=False)
    op.create_index(op.f('ix_class_teachers_class_id'), 'class_teachers', ['class_id'], unique=False)
    op.create_index(op.f('ix_class_teachers_teacher_id'), 'class_teachers', ['teacher_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_class_teachers_teacher_id'), table_name='class_teachers')
    op.drop_index(op.f('ix_class_teachers_class_id'), table_name='class_teachers')
    op.drop_index(op.f('ix_class_teachers_id'), table_name='class_teachers')
    op.drop_table('class_teachers')
