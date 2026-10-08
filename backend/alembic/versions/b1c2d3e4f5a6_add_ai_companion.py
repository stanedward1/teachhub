"""add ai companion tables

Revision ID: b1c2d3e4f5a6
Revises: a9b8c7d6e5f4
Create Date: 2026-09-30 12:00:00

AI 学伴（docs/DESIGN-AI学伴.md）P0 落库，一次迁移建齐 3 张表：

1. ``ai_companion_conversations`` —— 学伴会话（一学生 × 一作业 = 一会话）。
   带 ``school_id`` 参与 ORM 自动租户隔离；``(school_id, student_id, assignment_id)``
   唯一约束具名 ``uq_ai_companion_conv_scope``，**结构性保证**会话作用域。
2. ``ai_companion_messages`` —— 会话消息（user / assistant 逐条落库）。
   ``school_id`` 冗余存一份，使「查消息」直接受 ORM 租户过滤，无需 join 父会话。
3. ``ai_usage_daily_companion`` —— 学伴**独立**每日调用计数（平台级，**刻意不含
   ``school_id``**，与 ``ai_usage_daily`` 同口径：额度是平台级刹车，含了会让每校各
   一套额度 ⇒ 平台总花费变各校之和、刹车失效）。

外键全部 ``ondelete="CASCADE"``：会话随作业 / 学生删除而清除（用户决策 DC-3：
随作业级联删除、不设 TTL），不留孤儿。

方言安全：全为 ``create_table``（无 ``batch_alter_table`` 需求，三张表均为新建），
``created_at`` 用 ``sa.text('(CURRENT_TIMESTAMP)')``，紧跟 ``f3a4b5c6d7e8`` 的写法；
MySQL（开发/生产）与 SQLite（测试）通用。

🔴 具名约束必须与模型 ``__table_args__`` 完全一致（「迁移链 = 模型 schema」）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增学伴会话表、消息表与独立用量计数表。"""
    # 1. 学伴会话（一学生 × 一作业 = 一会话）
    op.create_table(
        'ai_companion_conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('school_id', sa.Integer(), nullable=True),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('turn_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        # 租户维度唯一约束：一学生在一份作业下只有一条会话（含 school_id，对齐 a7b8c9d0e1f2 先例）
        sa.UniqueConstraint(
            'school_id', 'student_id', 'assignment_id',
            name='uq_ai_companion_conv_scope',
        ),
    )
    op.create_index(op.f('ix_ai_companion_conversations_school_id'), 'ai_companion_conversations', ['school_id'], unique=False)
    op.create_index(op.f('ix_ai_companion_conversations_student_id'), 'ai_companion_conversations', ['student_id'], unique=False)
    op.create_index(op.f('ix_ai_companion_conversations_assignment_id'), 'ai_companion_conversations', ['assignment_id'], unique=False)

    # 2. 学伴消息（逐条落库，role = user / assistant）
    op.create_table(
        'ai_companion_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('school_id', sa.Integer(), nullable=True),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('refused', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('finish_reason', sa.String(32), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['ai_companion_conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ai_companion_messages_conversation_id'), 'ai_companion_messages', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_ai_companion_messages_school_id'), 'ai_companion_messages', ['school_id'], unique=False)

    # 3. 学伴独立每日用量（平台级，一天一行；刻意不含 school_id，同 ai_usage_daily 口径）
    op.create_table(
        'ai_usage_daily_companion',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('call_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('day', name='uq_ai_usage_daily_companion_day'),
    )


def downgrade() -> None:
    """回滚：逆序删除三张学伴表。

    🔴 **只 drop_table，不显式 drop_index**：MySQL 不允许先删「被外键依赖的索引」
    （`school_id` 上的索引同时支撑 `school_id` 外键，`DROP INDEX` 会报 1553
    "needed in a foreign key constraint"）。`DROP TABLE` 会连带删除该表自身的所有
    索引与外键，故按「先删子表、再删父表」的顺序 drop_table 即可，SQLite 同样适用。
    """
    op.drop_table('ai_usage_daily_companion')
    op.drop_table('ai_companion_messages')
    op.drop_table('ai_companion_conversations')
