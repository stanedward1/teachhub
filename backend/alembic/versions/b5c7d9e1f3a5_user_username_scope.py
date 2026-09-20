"""replace users unique(class_id, username) with role-aware username_scope unique

Revision ID: b5c7d9e1f3a5
Revises: a4b6c8d0e2f4
Create Date: 2026-09-20 20:45:00

背景：`uq_user_class_username (class_id, username)` 无法表达「按角色分叉」的唯一性口径——
教师 / 学校管理员的 `class_id` 为 NULL，而 MySQL / SQLite 都不把 NULL 计入唯一性判定，
导致这两类账号在数据库层**完全没有**唯一性约束，只剩应用层「先查后插」（存在并发竞态）。

修法：引入由 ORM 事件维护的 `username_scope` 列，改为 `UNIQUE (username_scope, username)`。
作用域口径：学生 `stu:<school>:<class>`、教师/校管 `staff:<school>`、平台超管 `platform`。

注意：本文件内的口径是**冻结快照**，刻意不 import `app.models.user`，
避免应用代码后续演进导致历史迁移的执行行为发生漂移。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5c7d9e1f3a5'
down_revision: Union[str, Sequence[str], None] = 'a4b6c8d0e2f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _scope_of(role, school_id, class_id) -> str:
    """与 `app.models.user.compute_username_scope` 同口径的冻结实现。"""
    if role == "student":
        return f"stu:{school_id or 0}:{class_id or 0}"
    if role in ("teacher", "school_admin"):
        return f"staff:{school_id}" if school_id is not None else "platform"
    return "platform"


def upgrade() -> None:
    # 1) 先加**可空**列。若直接 NOT NULL，MySQL 会把存量行填成空串，
    #    使所有历史行同处一个作用域，唯一索引大概率建不起来。
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('username_scope', sa.String(64), nullable=True))

    # 2) 逐行回填历史数据，口径与 ORM 事件完全一致
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, role, school_id, class_id FROM users")).fetchall()
    for uid, role, school_id, class_id in rows:
        conn.execute(
            sa.text("UPDATE users SET username_scope = :scope WHERE id = :uid"),
            {"scope": _scope_of(role, school_id, class_id), "uid": uid},
        )

    # 3) 收敛为非空 + 建立复合唯一约束（真正生效的那道）
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('username_scope', existing_type=sa.String(64), nullable=False)
        batch_op.create_unique_constraint('uq_user_scope_username', ['username_scope', 'username'])

    # 4) 摘掉旧约束。SQLite 建表时会把表级唯一约束落成自动索引（名字不可控），
    #    因此这里先探测再删，避免非 MySQL 方言下误报 "index does not exist"。
    insp = sa.inspect(op.get_bind())
    if 'uq_user_class_username' in {i['name'] for i in insp.get_indexes('users')}:
        with op.batch_alter_table('users') as batch_op:
            batch_op.drop_index('uq_user_class_username')


def downgrade() -> None:
    # 新口径对学生与旧口径等价、对教师/校管更严格，因此回滚不会遇到冲突数据
    with op.batch_alter_table('users') as batch_op:
        batch_op.create_unique_constraint('uq_user_class_username', ['class_id', 'username'])
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('uq_user_scope_username', type_='unique')
        batch_op.drop_column('username_scope')
