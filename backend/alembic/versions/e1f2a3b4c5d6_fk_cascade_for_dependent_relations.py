"""将纯从属关系外键 ON DELETE RESTRICT 改为 CASCADE

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-09-09 23:40:00

背景：作业链（assignments/submissions/excellent_works/work_comments/
submission_comments/assignment_attachments）与学生业务链（scores/attendance/
leaves/performances 等以 student_id 引用 students.id 的表）是「纯从属关系」，
子记录生命周期随父记录。改 CASCADE 后，删除父记录时数据库自动级联删除子记录，
无需代码手工清理，且可防止孤儿数据残留。

注意：归属/操作人关系（teacher_id/created_by/selected_by/changed_by 等）
与学校/班级删除关系保持 RESTRICT 不变，由代码 purge_* 显式处理。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 仅在 MySQL/PostgreSQL 等支持 ALTER 约束的库上生效；SQLite 不支持，跳过
    if op.get_bind().dialect.name == "sqlite":
        return
    op.drop_constraint('assignment_attachments_ibfk_1', 'assignment_attachments', type_='foreignkey')
    op.create_foreign_key('assignment_attachments_ibfk_1', 'assignment_attachments', 'assignments', ['assignment_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('submissions_ibfk_1', 'submissions', type_='foreignkey')
    op.create_foreign_key('submissions_ibfk_1', 'submissions', 'assignments', ['assignment_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('excellent_works_ibfk_2', 'excellent_works', type_='foreignkey')
    op.create_foreign_key('excellent_works_ibfk_2', 'excellent_works', 'submissions', ['submission_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('submission_comments_ibfk_1', 'submission_comments', type_='foreignkey')
    op.create_foreign_key('submission_comments_ibfk_1', 'submission_comments', 'submissions', ['submission_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('work_comments_ibfk_1', 'work_comments', type_='foreignkey')
    op.create_foreign_key('work_comments_ibfk_1', 'work_comments', 'excellent_works', ['excellent_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('attendance_ibfk_2', 'attendance', type_='foreignkey')
    op.create_foreign_key('attendance_ibfk_2', 'attendance', 'students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('communications_ibfk_1', 'communications', type_='foreignkey')
    op.create_foreign_key('communications_ibfk_1', 'communications', 'students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('leaves_ibfk_1', 'leaves', type_='foreignkey')
    op.create_foreign_key('leaves_ibfk_1', 'leaves', 'students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('performances_ibfk_1', 'performances', type_='foreignkey')
    op.create_foreign_key('performances_ibfk_1', 'performances', 'students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('return_records_ibfk_1', 'return_records', type_='foreignkey')
    op.create_foreign_key('return_records_ibfk_1', 'return_records', 'students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('scores_ibfk_1', 'scores', type_='foreignkey')
    op.create_foreign_key('scores_ibfk_1', 'scores', 'students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('student_board_history_ibfk_1', 'student_board_history', type_='foreignkey')
    op.create_foreign_key('student_board_history_ibfk_1', 'student_board_history', 'students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('student_comments_ibfk_1', 'student_comments', type_='foreignkey')
    op.create_foreign_key('student_comments_ibfk_1', 'student_comments', 'students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('student_profile_tags_ibfk_1', 'student_profile_tags', type_='foreignkey')
    op.create_foreign_key('student_profile_tags_ibfk_1', 'student_profile_tags', 'students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('submissions_student_id_fk', 'submissions', type_='foreignkey')
    op.create_foreign_key('submissions_student_id_fk', 'submissions', 'students', ['student_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('talks_ibfk_1', 'talks', type_='foreignkey')
    op.create_foreign_key('talks_ibfk_1', 'talks', 'students', ['student_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    # 仅在 MySQL/PostgreSQL 等支持 ALTER 约束的库上生效；SQLite 不支持，跳过
    if op.get_bind().dialect.name == "sqlite":
        return
    op.drop_constraint('talks_ibfk_1', 'talks', type_='foreignkey')
    op.create_foreign_key('talks_ibfk_1', 'talks', 'students', ['student_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('submissions_student_id_fk', 'submissions', type_='foreignkey')
    op.create_foreign_key('submissions_student_id_fk', 'submissions', 'students', ['student_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('student_profile_tags_ibfk_1', 'student_profile_tags', type_='foreignkey')
    op.create_foreign_key('student_profile_tags_ibfk_1', 'student_profile_tags', 'students', ['student_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('student_comments_ibfk_1', 'student_comments', type_='foreignkey')
    op.create_foreign_key('student_comments_ibfk_1', 'student_comments', 'students', ['student_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('student_board_history_ibfk_1', 'student_board_history', type_='foreignkey')
    op.create_foreign_key('student_board_history_ibfk_1', 'student_board_history', 'students', ['student_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('scores_ibfk_1', 'scores', type_='foreignkey')
    op.create_foreign_key('scores_ibfk_1', 'scores', 'students', ['student_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('return_records_ibfk_1', 'return_records', type_='foreignkey')
    op.create_foreign_key('return_records_ibfk_1', 'return_records', 'students', ['student_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('performances_ibfk_1', 'performances', type_='foreignkey')
    op.create_foreign_key('performances_ibfk_1', 'performances', 'students', ['student_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('leaves_ibfk_1', 'leaves', type_='foreignkey')
    op.create_foreign_key('leaves_ibfk_1', 'leaves', 'students', ['student_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('communications_ibfk_1', 'communications', type_='foreignkey')
    op.create_foreign_key('communications_ibfk_1', 'communications', 'students', ['student_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('attendance_ibfk_2', 'attendance', type_='foreignkey')
    op.create_foreign_key('attendance_ibfk_2', 'attendance', 'students', ['student_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('work_comments_ibfk_1', 'work_comments', type_='foreignkey')
    op.create_foreign_key('work_comments_ibfk_1', 'work_comments', 'excellent_works', ['excellent_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('submission_comments_ibfk_1', 'submission_comments', type_='foreignkey')
    op.create_foreign_key('submission_comments_ibfk_1', 'submission_comments', 'submissions', ['submission_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('excellent_works_ibfk_2', 'excellent_works', type_='foreignkey')
    op.create_foreign_key('excellent_works_ibfk_2', 'excellent_works', 'submissions', ['submission_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('submissions_ibfk_1', 'submissions', type_='foreignkey')
    op.create_foreign_key('submissions_ibfk_1', 'submissions', 'assignments', ['assignment_id'], ['id'], ondelete='RESTRICT')
    op.drop_constraint('assignment_attachments_ibfk_1', 'assignment_attachments', type_='foreignkey')
    op.create_foreign_key('assignment_attachments_ibfk_1', 'assignment_attachments', 'assignments', ['assignment_id'], ['id'], ondelete='RESTRICT')
