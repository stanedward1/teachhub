"""add school AI quota pools (ai_usage_daily_school / ai_usage_daily_companion_school)

Revision ID: f8a9b0c1d2e3
Revises: d6f7a8b9c0e1
Create Date: 2026-10-20 10:00:00

背景
----
「AI 能力以平台和学校为维度开启；以平台和学校为维度设置 AI 批改和 AI 学伴的
额度池（按调用次数计）」（docs/DESIGN-AI校级能力.md）。原「额度刻意不分校」
（DC-1）决策被本次需求推翻：平台池仍是全平台唯一总刹车（语义不变），新增
**校级池作为可选叠加层** —— 一次调用同时扣学校池和平台池，双池双闸门，任一
不足即拒。

本迁移**新增两张同构表**（沿用「每池一表一把行锁、互不阻塞」哲学，拒绝单表
kind 列 —— kind 会把两池的行锁合并到同一物理行集）：

* ``ai_usage_daily_school``              —— AI 批改校级池
* ``ai_usage_daily_companion_school``    —— AI 学伴校级池

结构（两表相同，参照平台池表 + 每生池表的 school_id 形态）
----
* ``id``          PK
* ``day``         Date, NOT NULL（数据库时钟当天，与平台池表同基准）
* ``school_id``   Integer, **NOT NULL**, FK ``schools.id``，INDEX
* ``call_count``  Integer, NOT NULL, server_default ``0``
* ``created_at``  DateTime, server_default now()
* ``updated_at``  DateTime

唯一约束 ``uq_ai_usage_daily_school_day_school`` /
``uq_ai_usage_daily_companion_school_day_school``： ``(day, school_id)``，
保证「每天每校一行」，也是并发首次创建的兜底。**不加其他租户列到唯一键**
—— ``schools.id`` 全局自增不跨校复用（与每生池 ``(day, student_id)`` 取舍相同）。

🔴 ``school_id`` **NOT NULL**：校池是学校维度的，写入方必须显式赋值（铁律 #6，
超管/后台线程上下文 ``before_flush`` 不回填，设计文档 §2.7 探针 [C] 实测）；
``school_id is None`` 的调用在代码层整段跳过校池逻辑，不触碰这两张表，
模型层 ``nullable=False`` 兜底。

纯建表，**无数据回填**（无行 = 不限 = 零迁移风险）。``settings`` 表零 schema 变更
（复用 ``(school_id, key)`` 唯一约束，运行时按需新增 ``school_ai_*`` 前缀 key 行）。

方言安全：全为 ``create_table``（无既有表 ALTER），``created_at`` 用
``sa.text('(CURRENT_TIMESTAMP)')``，与 ``d6f7a8b9c0e1`` 一致；MySQL（开发/生产）
与 SQLite（测试）通用。

🔴 具名约束必须与模型 ``__table_args__`` 完全一致（「迁移链 = 模型 schema」）。

幂等/可重跑：``upgrade()`` 开头检测表是否已存在，存在则跳过（允许开发中反复重跑）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, Sequence[str], None] = 'd6f7a8b9c0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE_GRADING = 'ai_usage_daily_school'
_UQ_GRADING = 'uq_ai_usage_daily_school_day_school'
_IX_GRADING_SCHOOL = 'ix_ai_usage_daily_school_school_id'

_TABLE_COMPANION = 'ai_usage_daily_companion_school'
_UQ_COMPANION = 'uq_ai_usage_daily_companion_school_day_school'
_IX_COMPANION_SCHOOL = 'ix_ai_usage_daily_companion_school_school_id'


def _table_exists(conn, table: str) -> bool:
    """检测表是否已存在（跨方言）。"""
    return sa.inspect(conn).has_table(table)


def _create_pool_table(table: str, uq_name: str, ix_school: str) -> None:
    """建一张校级池表（批改/学伴同构，仅表名与约束名不同）。"""
    op.create_table(
        table,
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        # 校池是学校维度的：NOT NULL，写入方显式赋值（见文件头说明）
        sa.Column('school_id', sa.Integer(), nullable=False),
        sa.Column('call_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=True,
        ),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id']),
        sa.PrimaryKeyConstraint('id'),
        # 每天每校一行（schools.id 全局自增不跨校复用，无需其他租户列）
        sa.UniqueConstraint('day', 'school_id', name=uq_name),
    )
    op.create_index(ix_school, table, ['school_id'], unique=False)


def upgrade() -> None:
    """新增两张校级额度池计数表（平台池不变，校池为可选叠加层）。"""
    conn = op.get_bind()
    if not _table_exists(conn, _TABLE_GRADING):
        _create_pool_table(_TABLE_GRADING, _UQ_GRADING, _IX_GRADING_SCHOOL)
        print(f"[f8a9b0c1d2e3] 已创建表 {_TABLE_GRADING}")
    else:
        # 已存在（重跑场景）：跳过，保证收敛。
        print(f"[f8a9b0c1d2e3] 表 {_TABLE_GRADING} 已存在，跳过 DDL")
    if not _table_exists(conn, _TABLE_COMPANION):
        _create_pool_table(_TABLE_COMPANION, _UQ_COMPANION, _IX_COMPANION_SCHOOL)
        print(f"[f8a9b0c1d2e3] 已创建表 {_TABLE_COMPANION}")
    else:
        print(f"[f8a9b0c1d2e3] 表 {_TABLE_COMPANION} 已存在，跳过 DDL")


def downgrade() -> None:
    """回滚：删除两张校级池表（依赖逆序，本处两表互不依赖，顺序无实质影响）。

    🔴 **只 drop_table，不显式 drop_index**：MySQL 不允许先删「被外键依赖的索引」
    （``school_id`` 上的索引同时支撑其外键，``DROP INDEX`` 会报 1553）。``DROP
    TABLE`` 会连带删除该表自身的所有索引与外键（对照 ``d6f7a8b9c0e1``）。
    """
    op.drop_table(_TABLE_COMPANION)
    op.drop_table(_TABLE_GRADING)
