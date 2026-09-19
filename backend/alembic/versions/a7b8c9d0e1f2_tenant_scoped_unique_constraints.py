"""将班级编码 / 学号 / 学生账号的全局唯一约束改为租户内唯一

Revision ID: a7b8c9d0e1f2
Revises: d5e6f7a8b9c0
Create Date: 2026-09-19 22:20:00

问题
----
三处唯一约束与多租户设计冲突：

1. ``classrooms.code`` 全局唯一
   不同学校无法复用同一套班级编码——两所学校都有「2024级计算机1班」时会被拒。

2. ``students.student_no`` 全局唯一
   不同学校无法出现相同学号。而各校独立编号（如都从 20240001 开始）是招生场景的常态，
   导入时会被误判为「学号已存在」。

3. ``users.username`` 此前**没有任何**唯一约束
   学生账号 ``username`` 即姓名，同一班级可能出现两个同名账号，登录时产生歧义。

处理
----
- 第 1、2 项改为 ``(school_id, x)`` 复合唯一。这是**放宽**约束：
  全局唯一 ⊆ 校内唯一，历史数据必然仍然满足，不会因迁移失败。
- 第 3 项新增 ``(class_id, username)`` 复合唯一。这是**收紧**约束，已核验库中 0 组重复；
  之所以按 ``class_id`` 而非 ``school_id``，是因为学生账号按「班级 + 姓名」定位、
  设计上允许跨班重名（见 ``app/models/user.py`` 注释）；且 ``class_id`` 为 NULL 的
  教师/管理员不受此约束（MySQL 中 NULL 不参与唯一性判定），其唯一性仍由应用层保证。

方言安全：用 Inspector 判断索引是否存在，同名索引跳过创建，
可在 SQLite（测试）与 MySQL（开发/生产）上执行。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(table: str) -> set:
    """返回指定表上已有的索引名集合（用于幂等判断）。"""
    insp = sa.inspect(op.get_bind())
    return {ix["name"] for ix in insp.get_indexes(table)}


def upgrade() -> None:
    # 1) classrooms：全局唯一 code → (school_id, code) 复合唯一
    names = _index_names("classrooms")
    if "code" in names:
        op.drop_index("code", table_name="classrooms")
    if "uq_classroom_school_code" not in names:
        op.create_index(
            "uq_classroom_school_code", "classrooms", ["school_id", "code"], unique=True
        )

    # 2) students：全局唯一 student_no → 普通索引（保留查询性能）
    #              + (school_id, student_no) 复合唯一
    names = _index_names("students")
    if "ix_students_student_no" in names:
        op.drop_index("ix_students_student_no", table_name="students")
        op.create_index("ix_students_student_no", "students", ["student_no"], unique=False)
    if "uq_student_school_no" not in names:
        op.create_index(
            "uq_student_school_no", "students", ["school_id", "student_no"], unique=True
        )

    # 3) users：新增 (class_id, username) 复合唯一
    names = _index_names("users")
    if "uq_user_class_username" not in names:
        op.create_index(
            "uq_user_class_username", "users", ["class_id", "username"], unique=True
        )


def downgrade() -> None:
    # 回滚到「全局唯一」的旧约束（仅恢复索引，不校验历史数据）
    names = _index_names("users")
    if "uq_user_class_username" in names:
        op.drop_index("uq_user_class_username", table_name="users")

    names = _index_names("students")
    if "uq_student_school_no" in names:
        op.drop_index("uq_student_school_no", table_name="students")
    if "ix_students_student_no" in names:
        op.drop_index("ix_students_student_no", table_name="students")
        op.create_index("ix_students_student_no", "students", ["student_no"], unique=True)

    names = _index_names("classrooms")
    if "uq_classroom_school_code" in names:
        op.drop_index("uq_classroom_school_code", table_name="classrooms")
    if "code" not in names:
        op.create_index("code", "classrooms", ["code"], unique=True)
