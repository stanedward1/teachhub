"""删除 id 字段的冗余索引 ix_<table>_id（主键本身已是索引）

Revision ID: c1d2e3f4a5b6
Revises: a3b4c5d6e7f8
Create Date: 2026-09-09 23:00:00

背景：所有模型 id 字段曾定义为 primary_key=True, index=True，
导致 MySQL 中 PRIMARY KEY(id) 之外又额外建了 ix_<table>_id 普通索引。
主键（InnoDB 聚簇索引）本身就是索引，这些 ix_<table>_id 完全冗余，
白白消耗存储与每次写入的索引维护成本。本迁移删除全部 33 个冗余索引。
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 删除 id 字段的冗余索引（保留 PRIMARY KEY）
    op.drop_index('ix_activities_id', table_name='activities')
    op.drop_index('ix_assignment_attachments_id', table_name='assignment_attachments')
    op.drop_index('ix_assignments_id', table_name='assignments')
    op.drop_index('ix_attendance_id', table_name='attendance')
    op.drop_index('ix_class_plans_id', table_name='class_plans')
    op.drop_index('ix_class_teachers_id', table_name='class_teachers')
    op.drop_index('ix_classrooms_id', table_name='classrooms')
    op.drop_index('ix_communications_id', table_name='communications')
    op.drop_index('ix_exams_id', table_name='exams')
    op.drop_index('ix_excellent_works_id', table_name='excellent_works')
    op.drop_index('ix_import_history_id', table_name='import_history')
    op.drop_index('ix_leaves_id', table_name='leaves')
    op.drop_index('ix_operation_logs_id', table_name='operation_logs')
    op.drop_index('ix_performances_id', table_name='performances')
    op.drop_index('ix_resources_id', table_name='resources')
    op.drop_index('ix_return_records_id', table_name='return_records')
    op.drop_index('ix_schedules_id', table_name='schedules')
    op.drop_index('ix_schools_id', table_name='schools')
    op.drop_index('ix_scores_id', table_name='scores')
    op.drop_index('ix_seats_id', table_name='seats')
    op.drop_index('ix_settings_id', table_name='settings')
    op.drop_index('ix_student_board_history_id', table_name='student_board_history')
    op.drop_index('ix_student_comments_id', table_name='student_comments')
    op.drop_index('ix_student_profile_tags_id', table_name='student_profile_tags')
    op.drop_index('ix_students_id', table_name='students')
    op.drop_index('ix_submission_comments_id', table_name='submission_comments')
    op.drop_index('ix_submissions_id', table_name='submissions')
    op.drop_index('ix_talks_id', table_name='talks')
    op.drop_index('ix_teacher_plans_id', table_name='teacher_plans')
    op.drop_index('ix_users_id', table_name='users')
    op.drop_index('ix_weekly_reports_id', table_name='weekly_reports')
    op.drop_index('ix_work_comments_id', table_name='work_comments')
    op.drop_index('ix_work_logs_id', table_name='work_logs')


def downgrade() -> None:
    # 回滚：重建这些 id 索引
    op.create_index('ix_activities_id', 'activities', ['id'])
    op.create_index('ix_assignment_attachments_id', 'assignment_attachments', ['id'])
    op.create_index('ix_assignments_id', 'assignments', ['id'])
    op.create_index('ix_attendance_id', 'attendance', ['id'])
    op.create_index('ix_class_plans_id', 'class_plans', ['id'])
    op.create_index('ix_class_teachers_id', 'class_teachers', ['id'])
    op.create_index('ix_classrooms_id', 'classrooms', ['id'])
    op.create_index('ix_communications_id', 'communications', ['id'])
    op.create_index('ix_exams_id', 'exams', ['id'])
    op.create_index('ix_excellent_works_id', 'excellent_works', ['id'])
    op.create_index('ix_import_history_id', 'import_history', ['id'])
    op.create_index('ix_leaves_id', 'leaves', ['id'])
    op.create_index('ix_operation_logs_id', 'operation_logs', ['id'])
    op.create_index('ix_performances_id', 'performances', ['id'])
    op.create_index('ix_resources_id', 'resources', ['id'])
    op.create_index('ix_return_records_id', 'return_records', ['id'])
    op.create_index('ix_schedules_id', 'schedules', ['id'])
    op.create_index('ix_schools_id', 'schools', ['id'])
    op.create_index('ix_scores_id', 'scores', ['id'])
    op.create_index('ix_seats_id', 'seats', ['id'])
    op.create_index('ix_settings_id', 'settings', ['id'])
    op.create_index('ix_student_board_history_id', 'student_board_history', ['id'])
    op.create_index('ix_student_comments_id', 'student_comments', ['id'])
    op.create_index('ix_student_profile_tags_id', 'student_profile_tags', ['id'])
    op.create_index('ix_students_id', 'students', ['id'])
    op.create_index('ix_submission_comments_id', 'submission_comments', ['id'])
    op.create_index('ix_submissions_id', 'submissions', ['id'])
    op.create_index('ix_talks_id', 'talks', ['id'])
    op.create_index('ix_teacher_plans_id', 'teacher_plans', ['id'])
    op.create_index('ix_users_id', 'users', ['id'])
    op.create_index('ix_weekly_reports_id', 'weekly_reports', ['id'])
    op.create_index('ix_work_comments_id', 'work_comments', ['id'])
    op.create_index('ix_work_logs_id', 'work_logs', ['id'])
