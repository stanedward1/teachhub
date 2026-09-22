"""补充 teacher_id 外键索引（按教师过滤的高频查询）

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-08 15:50:00

背景：work_logs/class_plans/teacher_plans/talks 按 teacher_id 做归属过滤，
classrooms.teacher_id 用于 is_teacher_class_owner 高频判断，均缺索引。
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEXES = [
    ("work_logs", "teacher_id"),
    ("class_plans", "teacher_id"),
    ("teacher_plans", "teacher_id"),
    ("talks", "teacher_id"),
    ("classrooms", "teacher_id"),
]


def upgrade() -> None:
    for table, col in _INDEXES:
        op.create_index(op.f(f"ix_{table}_{col}"), table, [col], unique=False)


def downgrade() -> None:
    for table, col in _INDEXES:
        op.drop_index(op.f(f"ix_{table}_{col}"), table_name=table)
