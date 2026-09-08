"""add is_graduated (classrooms) and is_dropped_out (students)

Revision ID: b7c4e2f1a9d8
Revises: a89fda91c31a
Create Date: 2026-08-26 10:20:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c4e2f1a9d8'
down_revision: Union[str, Sequence[str], None] = 'a89fda91c31a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('classrooms') as batch_op:
        batch_op.add_column(
            sa.Column('is_graduated', sa.Boolean(), nullable=False, server_default=sa.text('0'))
        )
    with op.batch_alter_table('students') as batch_op:
        batch_op.add_column(
            sa.Column('is_dropped_out', sa.Boolean(), nullable=False, server_default=sa.text('0'))
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('students') as batch_op:
        batch_op.drop_column('is_dropped_out')
    with op.batch_alter_table('classrooms') as batch_op:
        batch_op.drop_column('is_graduated')
