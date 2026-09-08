"""submissions.student_id 语义统一：users.id -> students.id，并补充外键索引

Revision ID: b2c3d4e5f6a7
Revises: f1a2b3c4d5e6
Create Date: 2026-09-08 13:00:00

背景：submissions.student_id 原本指向 users.id（学生登录账号），与 scores/talks/
performances 等业务表指向 students.id（学生档案）不一致，导致关联需 hack。
本次统一为 students.id，并补齐高频外键索引。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) submissions.student_id: users.id -> students.id（通过 class_id + name 映射）
    op.execute(
        """
        UPDATE submissions
        SET student_id = (
            SELECT st.id
            FROM users u
            JOIN students st ON st.class_id = u.class_id AND st.name = u.name
            WHERE u.id = submissions.student_id
        )
        WHERE student_id IN (SELECT id FROM users)
        """
    )

    # 2) 补充外键/高频查询索引
    op.create_index(op.f('ix_submissions_student_id'), 'submissions', ['student_id'], unique=False)
    op.create_index(op.f('ix_assignments_created_by'), 'assignments', ['created_by'], unique=False)
    op.create_index(op.f('ix_assignments_class_id'), 'assignments', ['class_id'], unique=False)
    op.create_index(op.f('ix_excellent_works_selected_by'), 'excellent_works', ['selected_by'], unique=False)
    op.create_index(op.f('ix_work_comments_user_id'), 'work_comments', ['user_id'], unique=False)
    op.create_index(op.f('ix_submission_comments_teacher_id'), 'submission_comments', ['teacher_id'], unique=False)


def downgrade() -> None:
    # 回滚索引
    op.drop_index(op.f('ix_submission_comments_teacher_id'), table_name='submission_comments')
    op.drop_index(op.f('ix_work_comments_user_id'), table_name='work_comments')
    op.drop_index(op.f('ix_excellent_works_selected_by'), table_name='excellent_works')
    op.drop_index(op.f('ix_assignments_class_id'), table_name='assignments')
    op.drop_index(op.f('ix_assignments_created_by'), table_name='assignments')
    op.drop_index(op.f('ix_submissions_student_id'), table_name='submissions')

    # 回滚 student_id 映射：students.id -> users.id
    op.execute(
        """
        UPDATE submissions
        SET student_id = (
            SELECT u.id
            FROM students st
            JOIN users u ON u.class_id = st.class_id AND u.name = st.name AND u.role = 'student'
            WHERE st.id = submissions.student_id
        )
        WHERE student_id IN (SELECT id FROM students)
        """
    )
