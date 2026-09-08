"""add class_id to operation_logs

Revision ID: a1b2c3d4e5f6
Revises: f9a8b7c6d5e4
Create Date: 2026-08-26 19:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f9a8b7c6d5e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('operation_logs') as batch_op:
        batch_op.add_column(sa.Column('class_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_operation_logs_class_id'), 'operation_logs', ['class_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_operation_logs_class_id'), table_name='operation_logs')
    with op.batch_alter_table('operation_logs') as batch_op:
        batch_op.drop_column('class_id')
