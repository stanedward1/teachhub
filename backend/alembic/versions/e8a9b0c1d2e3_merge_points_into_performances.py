"""积分模块合并入表现管理：performances 加 points 列，迁移历史积分后下线 points 表

Revision ID: e8a9b0c1d2e3
Revises: d4e5f6a7b8c9
Create Date: 2026-09-09 12:50:00

背景：积分管理与表现管理两模块功能约 90% 重叠（points.performance_id 外键即
同一业务重复建模），决定删除积分模块、保留表现管理。本迁移为收口迁移：
1. performances 表新增 points INTEGER NULL 列（正数加分/负数减分）；
2. 独立积分（performance_id IS NULL）→ INSERT 为新的表现记录；
3. 关联积分 → 回填到对应表现（取最新一条，防脏数据多条关联）；
4. 兜底：仍为 NULL 的表现按 ptype 补默认值（积极 +1 / 消极 -1）；
5. drop_table('points')（SQLite/MySQL 下 drop 连带删索引与外键）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8a9b0c1d2e3'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) performances 新增 points 列（batch_alter_table 兼容 SQLite/MySQL）
    with op.batch_alter_table("performances") as batch_op:
        batch_op.add_column(sa.Column("points", sa.Integer(), nullable=True))

    # 2) 独立积分 → INSERT 为新的表现记录（ptype 按 points 正负映射，content = reason）
    op.execute(
        """
        INSERT INTO performances (student_id, school_id, ptype, content, image, created_at, points)
        SELECT pt.student_id,
               pt.school_id,
               CASE WHEN pt.points >= 0 THEN '积极' ELSE '消极' END,
               COALESCE(pt.reason, ''),
               NULL,
               pt.created_at,
               pt.points
        FROM points pt
        WHERE pt.performance_id IS NULL
        """
    )

    # 3) 关联积分 → 回填到对应表现（取该表现最新一条积分，防脏数据多条关联）
    op.execute(
        """
        UPDATE performances
        SET points = (
            SELECT pt.points FROM points pt
            WHERE pt.performance_id = performances.id
            ORDER BY pt.id DESC
            LIMIT 1
        )
        WHERE points IS NULL
        """
    )

    # 4) 兜底：历史上没联动积分的表现，按 ptype 补默认值（消极 -1 / 积极 +1）
    op.execute("UPDATE performances SET points = -1 WHERE points IS NULL AND ptype = '消极'")
    op.execute("UPDATE performances SET points = 1 WHERE points IS NULL")

    # 5) 下线 points 表（drop 连带删除索引与外键）
    op.drop_table("points")


def downgrade() -> None:
    """尽力而为回滚：重建空 points 表 + 删除 performances.points 列（数据不还原）。"""
    op.create_table(
        "points",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=True),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reason", sa.String(length=255)),
        sa.Column("performance_id", sa.Integer(), sa.ForeignKey("performances.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(op.f("ix_points_id"), "points", ["id"], unique=False)
    op.create_index(op.f("ix_points_student_id"), "points", ["student_id"], unique=False)
    op.create_index(op.f("ix_points_school_id"), "points", ["school_id"], unique=False)

    with op.batch_alter_table("performances") as batch_op:
        batch_op.drop_column("points")
