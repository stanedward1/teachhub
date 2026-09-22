"""为高频过滤字段补充索引（阶段一 Quick Wins - B2 性能优化）

Revision ID: f2c3d4e5a6b7
Revises: e8a9b0c1d2e3
Create Date: 2026-09-09 19:50:00

背景：以下字段是列表接口 / 登录接口 / 权限判断的高频 filter 条件，此前缺索引，
导致全表扫描（SQLite/MySQL 下 count + 过滤双查询会随数据量线性变慢）：

- scores.subject         按科目过滤成绩（成绩列表 / 统计）
- scores.exam_name       按考试名过滤成绩
- users.role             登录定位、权限判断按 role 过滤
- users.class_id         按班级查学生账号
- students.school_id     花名册按学校隔离（最高频）
- students.class_id      花名册按班级过滤（最高频）
- classrooms.school_id   按学校查班级列表
- attendance.status      按考勤状态过滤（出勤/缺勤/请假/迟到）
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f2c3d4e5a6b7'
down_revision: Union[str, Sequence[str], None] = 'e8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEXES = [
    ("scores", "subject"),
    ("scores", "exam_name"),
    ("users", "role"),
    ("users", "class_id"),
    ("students", "school_id"),
    ("students", "class_id"),
    ("classrooms", "school_id"),
    ("attendance", "status"),
]


def upgrade() -> None:
    for table, col in _INDEXES:
        op.create_index(op.f(f"ix_{table}_{col}"), table, [col], unique=False)


def downgrade() -> None:
    for table, col in _INDEXES:
        op.drop_index(op.f(f"ix_{table}_{col}"), table_name=table)
