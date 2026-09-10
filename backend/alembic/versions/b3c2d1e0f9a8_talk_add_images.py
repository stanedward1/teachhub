"""talk add images (multi-image JSON array)

Revision ID: b3c2d1e0f9a8
Revises: a9f8e7d6c5b4
Create Date: 2026-09-10 15:20:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c2d1e0f9a8'
down_revision: Union[str, Sequence[str], None] = 'a9f8e7d6c5b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """给 talks 表加 images 列（Text，存多张配图的 JSON 数组字符串）。"""
    with op.batch_alter_table('talks') as batch_op:
        batch_op.add_column(sa.Column('images', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('talks') as batch_op:
        batch_op.drop_column('images')
