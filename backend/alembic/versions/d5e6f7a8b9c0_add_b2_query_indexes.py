"""补齐 B2 列表明细接口的缺口组合索引（阶段二 性能优化）

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-19 13:30:00

审计结论（仅补真实缺失、且能被既有查询命中的索引，避免重复建索引）：

1. submissions(assignment_id, student_id)
   作业提交存在性检查 ``WHERE assignment_id=? AND student_id=?``（学生重复提交判定、
   教师按作业查看某生提交）为高频 AND 查询。现有 ix_submissions_assignment_id 与
   ix_submissions_student_id 均单列，本组合索引可一次性命中两列。

2. scores(student_id, subject)
   成绩列表 ``WHERE student_id IN (...) AND subject=?``、成绩分析按科目排名同型。
   现有 ix_scores_student_id、ix_scores_subject 均单列，组合后减少回表。

3. leaves(student_id, status)
   请假列表 ``WHERE student_id IN (...) AND status=?``（状态筛选为可选过滤）。
   现有仅 ix_leaves_student_id，status 无索引。

4. operation_logs(created_at)
   审计日志按时间范围查询 ``WHERE created_at >= since`` 及
   ``created_at BETWEEN start AND end``（默认近 N 天报表），created_at 此前无索引。

方言安全：仅使用 op.create_index / op.drop_index 与 SQLAlchemy Inspector 做存在性
判断，可在 SQLite（测试）与 MySQL（开发）上执行；已存在同名索引时跳过，避免
MySQL 重复索引报错。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (索引名, 表名, [列...])
_INDEXES = [
    ("ix_submissions_assignment_id_student_id", "submissions", ["assignment_id", "student_id"]),
    ("ix_scores_student_id_subject", "scores", ["student_id", "subject"]),
    ("ix_leaves_student_id_status", "leaves", ["student_id", "status"]),
    ("ix_operation_logs_created_at", "operation_logs", ["created_at"]),
]


def _index_exists(table: str, name: str) -> bool:
    """判断指定表上是否已存在同名索引（方言无关，失败时保守返回 False）。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        existing = {ix.get("name") for ix in inspector.get_indexes(table)}
    except Exception:
        return False
    return name in existing


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        if not _index_exists(table, name):
            op.create_index(name, table, columns, unique=False)


def downgrade() -> None:
    for name, table, columns in _INDEXES:
        if _index_exists(table, name):
            op.drop_index(name, table_name=table)
