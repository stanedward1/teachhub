"""add ai_companion_usage_daily_student (per-student quota)

Revision ID: d6f7a8b9c0e1
Revises: c5e6f7a8b9d0
Create Date: 2026-10-07 10:00:00

背景
----
AI 学伴此前只有**平台池**额度（``ai_usage_daily_companion``，一天一行，跨所有学生，
成本刹车）。需求要为**每个学生**各自一份「一天能问多少次」的配额（公平语义），
且与学生端「今日剩余 N 次」的实时提示配套（docs/DESIGN-AI学伴配额.md D1/D2）。

本迁移**新增一张独立表** ``ai_companion_usage_daily_student`` 承载每生配额，
**一行不动**既有平台池表 —— 两层额度叠加、独立表独立锁（与「批改/学伴两表两锁」
的既有先例同构）。

结构
----
* ``id``            PK
* ``day``           Date, NOT NULL（数据库时钟当天，与平台池表同基准）
* ``student_id``    Integer, NOT NULL, FK ``students.id`` ``ondelete=CASCADE``，INDEX
* ``school_id``     Integer, NULL, FK ``schools.id``，INDEX（纳入 ORM 租户隔离）
* ``call_count``    Integer, NOT NULL, server_default ``0``
* ``created_at``    DateTime, server_default now()
* ``updated_at``    DateTime

唯一约束 ``uq_ai_companion_usage_daily_student (day, student_id)``：保证「每天每生一行」，
也是并发首次创建的兜底。**不加 school_id 到唯一键** —— ``student_id`` 全局唯一
（``students.id`` 主键全局自增、不跨校复用），加 school_id 冗余且会误导「跨校同 id」。

🔴 ``school_id`` 语义：本表带 school_id ⇒ 会被 ORM 自动注入 ``school_id=当前租户``；
写入时应用层**显式取父资源（``student.school_id``）赋值**，不依赖 ``before_flush``
回填（超管上下文 school_id=None 不回填，落 NULL 就对所有租户不可见）。

方言安全：全为 ``create_table``（无既有表 ALTER），``created_at`` 用
``sa.text('(CURRENT_TIMESTAMP)')``，与 ``b1c2d3e4f5a6`` 一致；MySQL（开发/生产）
与 SQLite（测试）通用。

🔴 具名约束必须与模型 ``__table_args__`` 完全一致（「迁移链 = 模型 schema」）。

幂等/可重跑：``upgrade()`` 开头检测表是否已存在，存在则跳过（允许开发中反复重跑）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6f7a8b9c0e1'
down_revision: Union[str, Sequence[str], None] = 'c5e6f7a8b9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE = 'ai_companion_usage_daily_student'
_UQ_NAME = 'uq_ai_companion_usage_daily_student'
_IX_STUDENT = 'ix_ai_companion_usage_daily_student_student_id'
_IX_SCHOOL = 'ix_ai_companion_usage_daily_student_school_id'


def _table_exists(conn, table: str) -> bool:
    """检测表是否已存在（跨方言）。"""
    return sa.inspect(conn).has_table(table)


def upgrade() -> None:
    """新增每生独立配额计数表（与平台池表并存，叠加生效）。"""
    conn = op.get_bind()
    if _table_exists(conn, _TABLE):
        # 已存在（重跑场景）：跳过，保证收敛。
        print(f"[d6f7a8b9c0e1] 表 {_TABLE} 已存在，跳过 DDL")
        return

    op.create_table(
        _TABLE,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('school_id', sa.Integer(), nullable=True),
        sa.Column('call_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=True,
        ),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id']),
        sa.PrimaryKeyConstraint('id'),
        # 每天每生一行（student_id 全局唯一，无需含 school_id）
        sa.UniqueConstraint('day', 'student_id', name=_UQ_NAME),
    )
    op.create_index(_IX_STUDENT, _TABLE, ['student_id'], unique=False)
    op.create_index(_IX_SCHOOL, _TABLE, ['school_id'], unique=False)
    print(f"[d6f7a8b9c0e1] 已创建表 {_TABLE}")


def downgrade() -> None:
    """回滚：删除每生配额表。

    🔴 **只 drop_table，不显式 drop_index**：MySQL 不允许先删「被外键依赖的索引」
    （``school_id`` 上的索引同时支撑其外键，``DROP INDEX`` 会报 1553
    "needed in a foreign key constraint"）。``DROP TABLE`` 会连带删除该表自身的所有
    索引与外键，故直接 drop_table 即可，SQLite 同样适用（对照 ``b1c2d3e4f5a6``）。
    """
    op.drop_table(_TABLE)
