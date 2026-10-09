"""为 created_at 排序/范围过滤路径与 AI 批改状态过滤补索引（B2 性能优化）

Revision ID: b7c8d9e0f1a2
Revises: f8a9b0c1d2e3
Create Date: 2026-10-09 10:00:00

背景：其余表的 created_at 此前均无索引，但存在真实的排序/范围过滤消费者；
只给**有消费者**的表建索引（先 grep 后建，不盲加）。

注意：operation_logs.created_at 的范围过滤（audit_log_stats / list_audit_logs）
虽是消费者，但其索引已由既有迁移 d5e6f7a8b9c0 创建（ix_operation_logs_created_at），
此处**不重复创建**，模型上以 index=True 与库内实况对齐。

- scores.created_at           成绩按 created_at 排序（工作台档案/成绩趋势/最新一条）
- leaves.created_at           请假列表按 created_at 倒序（admin_service）
- assignments.created_at      作业列表按 created_at 倒序（homework_service）
- submissions.created_at      提交列表按 created_at 倒序（homework_service）
- excellent_works.created_at  优秀作品按 created_at 倒序（homework_service）
- work_comments.created_at    作品评语按 created_at 升序（homework_service）
- student_board_history.created_at  板报履历按 created_at 升序（students_service）
- performances.created_at     表现记录按 `created_at >= week_start` 范围过滤
                              （workbench/reports_service）
- ai_grading_results.status   批改统计/单份重批守卫按 status 过滤
                              （ai_grading / homework_service）

命名遵循既有风格 ``ix_<table>_<column>``，均不超 MySQL 64 字符限制。
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEXES = [
    ("scores", "created_at"),
    ("leaves", "created_at"),
    ("assignments", "created_at"),
    ("submissions", "created_at"),
    ("excellent_works", "created_at"),
    ("work_comments", "created_at"),
    ("student_board_history", "created_at"),
    ("performances", "created_at"),
    ("ai_grading_results", "status"),
]


def upgrade() -> None:
    for table, col in _INDEXES:
        op.create_index(op.f(f"ix_{table}_{col}"), table, [col], unique=False)


def downgrade() -> None:
    for table, col in _INDEXES:
        op.drop_index(op.f(f"ix_{table}_{col}"), table_name=table)
