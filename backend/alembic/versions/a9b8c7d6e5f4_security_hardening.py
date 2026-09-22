"""security hardening: ai usage counter, token_version, one submission per student

Revision ID: a9b8c7d6e5f4
Revises: f3a4b5c6d7e8
Create Date: 2026-09-22 21:30:00

三处变更，均来自代码审阅（docs/REVIEW-2026-09-22-code-audit.md）：

1. **`ai_usage_daily`（新表）** —— AI 批改按**实际外呼次数**计额度。
   原先用「当日 `ai_grading_results` 行数」近似，可被绕过：同一提交重跑是 `upsert`
   （覆盖同一行）⇒ 不增计数；学生重交会删结果行 ⇒ 计数回退。独立计数表与结果行
   生命周期解耦，且额度改为**投递前原子预留**（`FOR UPDATE`），并发不再超发。
   平台级数据，刻意不含 `school_id`（与 `ai_credentials` 同理）。

2. **`users.token_version`（新列）** —— access token 可吊销。
   access token 是无状态 JWT，无法逐个撤销；把 `users.token_version` 写进令牌的
   `tv` 声明，改密 / 重置密码时 +1，校验端（`app/deps.py`）比对即可让该账号此前
   签发的**全部** access token 立刻失效。存量为 0，升级前签发的老 token 无 `tv`
   声明按 0 处理，因此本次升级**不会**强制全体重新登录。

3. **`uq_submission_assignment_student`（唯一索引）** —— 一名学生在一份作业下
   只允许一条提交。应用层 `submit` 是「先查后改」，首次提交并发时两个请求可能
   双双查不到而各插一行；本索引兜底，`submit` 捕获冲突后退化为更新（返回 200）。
   迁移前已核对线上数据无重复（`GROUP BY ... HAVING COUNT(*) > 1` 为空）。

方言安全：`batch_alter_table` 包裹加列 / 加约束，MySQL（开发/生产）与 SQLite
（测试环境 `run_migrations()` 同样会执行迁移）通用。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, Sequence[str], None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增每日用量表、会话版本列与提交唯一索引。"""
    # 1. AI 批改每日调用计数（平台级，一天一行）
    op.create_table(
        'ai_usage_daily',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('call_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        # 一天一行：既是业务不变量，也是并发首次创建的兜底
        sa.UniqueConstraint('day', name='uq_ai_usage_daily_day'),
    )

    # 2. 会话版本号（存量行回填 0）
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('token_version', sa.Integer(), nullable=False, server_default='0')
        )

    # 3. 一名学生在一份作业下只允许一条提交（并发双击的数据库层兜底）
    with op.batch_alter_table('submissions') as batch_op:
        batch_op.create_unique_constraint(
            'uq_submission_assignment_student', ['assignment_id', 'student_id']
        )


def downgrade() -> None:
    """回滚：删除唯一索引、会话版本列与每日用量表。"""
    with op.batch_alter_table('submissions') as batch_op:
        batch_op.drop_constraint('uq_submission_assignment_student', type_='unique')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('token_version')

    op.drop_table('ai_usage_daily')
