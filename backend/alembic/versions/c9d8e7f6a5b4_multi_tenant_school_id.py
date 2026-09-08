"""multi-tenant: add school_id to users and business tables

Revision ID: c9d8e7f6a5b4
Revises: b6d5e4f3a2c1
Create Date: 2026-09-07 23:50:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d8e7f6a5b4'
down_revision: Union[str, Sequence[str], None] = 'b6d5e4f3a2c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 需要加 school_id 的业务表（users/schools 单独处理）
BUSINESS_TABLES = [
    # homework
    'assignments', 'submissions', 'excellent_works', 'work_comments', 'submission_comments',
    # workbench
    'scores', 'leaves', 'points', 'communications', 'resources', 'exams', 'seats',
    'import_history', 'student_profile_tags', 'weekly_reports', 'student_board_history',
    'attendance', 'settings',
    # classlog
    'work_logs', 'class_plans', 'teacher_plans', 'schedules', 'activities', 'talks',
    'return_records', 'performances', 'student_comments',
    # operation
    'operation_logs',
]


def upgrade() -> None:
    """多租户改造：加 school_id 列、回填默认租户、admin 迁移为 super_admin。"""
    # 1. schools 加 status、created_by
    with op.batch_alter_table('schools') as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(20), nullable=False, server_default=sa.text("'active'")))
        batch_op.add_column(sa.Column('created_by', sa.Integer(), nullable=True))

    # 2. users 加 school_id
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('school_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_users_school_id'), 'users', ['school_id'], unique=False)

    # 3. 业务表加 school_id + 索引
    for t in BUSINESS_TABLES:
        with op.batch_alter_table(t) as batch_op:
            batch_op.add_column(sa.Column('school_id', sa.Integer(), nullable=True))
        op.create_index(op.f(f'ix_{t}_school_id'), t, ['school_id'], unique=False)

    # 4. 回填 school_id（默认租户 = schools 第一条）
    for t in BUSINESS_TABLES:
        op.execute(
            f"UPDATE {t} SET school_id = (SELECT id FROM schools ORDER BY id LIMIT 1) "
            "WHERE school_id IS NULL"
        )
    # users 回填（排除 admin，它即将变为 super_admin，school_id 保持 NULL）
    op.execute(
        "UPDATE users SET school_id = (SELECT id FROM schools ORDER BY id LIMIT 1) "
        "WHERE school_id IS NULL AND role != 'admin'"
    )

    # 5. role 迁移：admin -> super_admin
    op.execute("UPDATE users SET role = 'super_admin' WHERE role = 'admin'")


def downgrade() -> None:
    # role 恢复
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'super_admin'")
    # drop school_id 列（业务表 + users + schools 字段）
    for t in BUSINESS_TABLES:
        op.drop_index(op.f(f'ix_{t}_school_id'), table_name=t)
        with op.batch_alter_table(t) as batch_op:
            batch_op.drop_column('school_id')
    op.drop_index(op.f('ix_users_school_id'), table_name='users')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('school_id')
    with op.batch_alter_table('schools') as batch_op:
        batch_op.drop_column('created_by')
        batch_op.drop_column('status')
