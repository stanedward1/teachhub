"""修复 submissions.student_id 外键：users.id -> students.id

Revision ID: a3b4c5d6e7f8
Revises: f2c3d4e5a6b7
Create Date: 2026-09-09 21:20:00

背景：submissions.student_id 的语义在 b2c3d4e5f6a7 迁移中已从 users.id
统一为 students.id，但该迁移只更新了数据 + 建索引，**漏删了旧外键**
（submissions_ibfk_2 仍指向 users.id）。

后果：SQLite 因默认关闭外键而未暴露；但 MySQL（InnoDB 强制外键）在删除
学生账号（users）时，会因 submissions.student_id 残留指向 users.id 的外键
约束而报 1451（Cannot delete or update a parent row），导致 DELETE
/api/admin/users/{id} 返回 500。

本迁移删除错误外键并重建为指向 students.id。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'f2c3d4e5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 仅在 MySQL/PostgreSQL 等强制外键的库上生效；SQLite 无此约束则跳过
    # 删除旧外键 submissions_ibfk_2（student_id -> users.id）
    op.execute("ALTER TABLE submissions DROP FOREIGN KEY submissions_ibfk_2")
    # 重建正确外键（student_id -> students.id）
    op.create_foreign_key(
        'submissions_student_id_fk',
        'submissions',
        'students',
        ['student_id'],
        ['id'],
    )


def downgrade() -> None:
    # 回滚：删新外键，重建旧外键（student_id -> users.id）
    op.execute("ALTER TABLE submissions DROP FOREIGN KEY submissions_student_id_fk")
    op.create_foreign_key(
        'submissions_ibfk_2',
        'submissions',
        'users',
        ['student_id'],
        ['id'],
    )
