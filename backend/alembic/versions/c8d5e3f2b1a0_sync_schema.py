"""sync schema: add users/exams columns and missing tables

Revision ID: c8d5e3f2b1a0
Revises: b7c4e2f1a9d8
Create Date: 2026-08-26 11:20:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d5e3f2b1a0'
down_revision: Union[str, Sequence[str], None] = 'b7c4e2f1a9d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 补齐 users 安全策略字段（首次登录改密 + 登录失败锁定）
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))

    # 补齐 exams 文件字段
    with op.batch_alter_table('exams') as batch_op:
        batch_op.add_column(sa.Column('filename', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('filepath', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('filesize', sa.Integer(), nullable=True, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('filetype', sa.String(20), nullable=True))

    # 补齐缺失的表
    op.create_table('submission_comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_submission_comments_id'), 'submission_comments', ['id'], unique=False)
    op.create_index(op.f('ix_submission_comments_submission_id'), 'submission_comments', ['submission_id'], unique=False)

    op.create_table('import_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('import_type', sa.String(20), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('total_rows', sa.Integer(), nullable=True),
        sa.Column('success_rows', sa.Integer(), nullable=True),
        sa.Column('error_rows', sa.Integer(), nullable=True),
        sa.Column('errors', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_import_history_id'), 'import_history', ['id'], unique=False)
    op.create_index(op.f('ix_import_history_import_type'), 'import_history', ['import_type'], unique=False)

    op.create_table('student_profile_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('tag', sa.String(50), nullable=False),
        sa.Column('category', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_student_profile_tags_id'), 'student_profile_tags', ['id'], unique=False)
    op.create_index(op.f('ix_student_profile_tags_student_id'), 'student_profile_tags', ['student_id'], unique=False)

    op.create_table('weekly_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('class_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('week_start', sa.String(20), nullable=True),
        sa.Column('week_end', sa.String(20), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('data_snapshot', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['class_id'], ['classrooms.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_weekly_reports_id'), 'weekly_reports', ['id'], unique=False)
    op.create_index(op.f('ix_weekly_reports_class_id'), 'weekly_reports', ['class_id'], unique=False)

    op.create_table('student_board_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('old_type', sa.String(20), nullable=True),
        sa.Column('new_type', sa.String(20), nullable=False),
        sa.Column('changed_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_student_board_history_id'), 'student_board_history', ['id'], unique=False)
    op.create_index(op.f('ix_student_board_history_student_id'), 'student_board_history', ['student_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_student_board_history_student_id'), table_name='student_board_history')
    op.drop_index(op.f('ix_student_board_history_id'), table_name='student_board_history')
    op.drop_table('student_board_history')
    op.drop_index(op.f('ix_weekly_reports_class_id'), table_name='weekly_reports')
    op.drop_index(op.f('ix_weekly_reports_id'), table_name='weekly_reports')
    op.drop_table('weekly_reports')
    op.drop_index(op.f('ix_student_profile_tags_student_id'), table_name='student_profile_tags')
    op.drop_index(op.f('ix_student_profile_tags_id'), table_name='student_profile_tags')
    op.drop_table('student_profile_tags')
    op.drop_index(op.f('ix_import_history_import_type'), table_name='import_history')
    op.drop_index(op.f('ix_import_history_id'), table_name='import_history')
    op.drop_table('import_history')
    op.drop_index(op.f('ix_submission_comments_submission_id'), table_name='submission_comments')
    op.drop_index(op.f('ix_submission_comments_id'), table_name='submission_comments')
    op.drop_table('submission_comments')
    with op.batch_alter_table('exams') as batch_op:
        batch_op.drop_column('filetype')
        batch_op.drop_column('filesize')
        batch_op.drop_column('filepath')
        batch_op.drop_column('filename')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('locked_until')
        batch_op.drop_column('failed_attempts')
        batch_op.drop_column('must_change_password')
