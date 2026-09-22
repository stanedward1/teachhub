"""add ai grading tables and excellent_works.source

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-09-22 03:10:00

AI 作业批改（docs/AI-GRADING-PRD.md）P0 落库，三处变更：

1. `ai_credentials` —— 平台级 AI 服务凭证。
   **刻意不含 `school_id` 列**：凭证是平台资产，只有平台超管能配置与查看，安全性由接口
   依赖 `require_super_admin` 保证。不带该列也就不会被 ORM 租户过滤器命中
   （`tenant.py::_tenant_models` 只收集含 `school_id` 的映射类），任何租户上下文下都可读。
   这也顺带绕开 `settings` 表存密钥的三个坑：`GET /api/settings` 明文返回全部配置、
   `Setting.value` 仅 String(255) 容量不足、`uq_settings_school_key` 对 NULL 唯一失效。
2. `ai_grading_results` —— AI 批改结果，`submission_id` 唯一（一个提交一条，重跑覆盖），
   带 `school_id` 参与 ORM 自动租户隔离。
3. `excellent_works.source` —— 区分人工评选（`manual`）与 AI 推荐（`ai_recommended`）。
   存量行由 `server_default='manual'` 回填，既有语义与展示链路完全不变。
   `selected_by`（NOT NULL）语义不变：始终记「执行入库的人」。

方言安全：`batch_alter_table` 包裹加列，MySQL（开发/生产）与 SQLite（测试）通用。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """新增 AI 凭证表、批改结果表，并为优秀作品加来源标识。"""
    op.create_table(
        'ai_credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('base_url', sa.String(255), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('api_key_encrypted', sa.Text(), nullable=False),
        sa.Column('vision_enabled', sa.Boolean(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'ai_grading_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('submission_id', sa.Integer(), nullable=False),
        sa.Column('school_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('provider', sa.String(50), nullable=True),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('strengths', sa.Text(), nullable=True),
        sa.Column('improvements', sa.Text(), nullable=True),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('attachment_used', sa.String(255), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('is_excellent_candidate', sa.Boolean(), nullable=False),
        sa.Column('excellent_reason', sa.Text(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
        sa.PrimaryKeyConstraint('id'),
        # 一个提交一条：重跑覆盖，天然幂等
        sa.UniqueConstraint('submission_id', name='uq_ai_grading_submission'),
    )
    op.create_index(op.f('ix_ai_grading_results_school_id'), 'ai_grading_results', ['school_id'], unique=False)

    with op.batch_alter_table('excellent_works') as batch_op:
        batch_op.add_column(
            sa.Column('source', sa.String(20), nullable=False, server_default='manual')
        )


def downgrade() -> None:
    """回滚：删除来源标识与两张 AI 表。"""
    with op.batch_alter_table('excellent_works') as batch_op:
        batch_op.drop_column('source')

    op.drop_index(op.f('ix_ai_grading_results_school_id'), table_name='ai_grading_results')
    op.drop_table('ai_grading_results')
    op.drop_table('ai_credentials')
