"""activity filepath -> Text (multi-image JSON array)

Revision ID: a9f8e7d6c5b4
Revises: a1b2c3d4e5f6
Create Date: 2026-09-10 14:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9f8e7d6c5b4'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """把 activities.filepath 从 String(500) 改为 Text，以容纳多张配图的 JSON 数组。"""
    with op.batch_alter_table('activities') as batch_op:
        batch_op.alter_column('filepath',
                              existing_type=sa.String(500),
                              type_=sa.Text(),
                              existing_nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('activities') as batch_op:
        batch_op.alter_column('filepath',
                              existing_type=sa.Text(),
                              type_=sa.String(500),
                              existing_nullable=True)
