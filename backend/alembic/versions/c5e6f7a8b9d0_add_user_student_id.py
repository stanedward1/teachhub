"""add users.student_id hard link to students

Revision ID: c5e6f7a8b9d0
Revises: b1c2d3e4f5a6
Create Date: 2026-10-06 10:00:00

背景
----
``users``（登录账号）与 ``students``（学生档案）此前**没有任何外键**，二者靠
``(class_id, name)`` 两字段软匹配互相定位。这带来两个已确认缺陷：

1. 同班两个同名学生会命中错人（软匹配一律 ``.first()``）——AI 学伴会话/配额
   会串到别人身上（``app/services/ai_companion.py::_resolve_student``）。
2. 学生改名后软匹配失配（档案改了名、账号 name 未同步，或反之）。

本迁移为学生账号补一把**稳定的身份锚点**：``users.student_id -> students.id``，
使「账号 ↔ 档案」成为可持久、可唯一定位的关系。这也是「AI 学伴按学生独立计数配额」
的前置——配额要按学生独立，身份必须先唯一稳定。

结构变更
--------
* ``users.student_id``：``Integer, nullable=True``，外键 ``students.id``。
  - **可空是刻意的**：非学生角色（teacher / school_admin / super_admin）该列恒为
    NULL；学生账号在「档案尚未建立」或迁移期冲突时也允许暂空（回落软匹配）。
  - ``ondelete="SET NULL"``：``Student`` 是**档案**、``User`` 是**账号**，二者生命
    周期不应强绑。删除学生档案不应连带删除登录账号（账号还挂着登录历史、审计、
    可能的人工复核诉求）；把外键置空、由业务决定账号去留，是最保守且可逆的选择。
    对比 ``CASCADE``（删档案即删账号）会把「误删档案」放大成「账号也没了」。
* ``ix_users_student_id``：普通索引。定位场景如
  ``get_student_avatar``（由档案反查账号头像）需要按 ``student_id`` 查 users；
  MySQL 外键本身要求索引，此处显式具名为模型 ``index=True`` 对齐。
  **非唯一**：一个学生档案理论上可能对应多个账号（历史遗留/重复导入），迁移期不
  为「数据库从未保证过」的口径强加唯一约束，避免把潜在脏数据升级成迁移失败。

回填
----
把 ``role='student'`` 的行按 ``(class_id, name)`` 匹配到 ``students.id`` 写回。

🔴 **冲突安全策略**：若某 ``(class_id, name)`` 在 ``students`` 里对应**多行**，
说明软匹配本身有歧义，此时**跳过不填**（保持 NULL 待人工处理），绝不 ``LIMIT 1``
随便取一行——那正是本次要修复的「命中错人」缺陷。迁移会打印
「回填 N 行 / 跳过 M 行（冲突）」日志。同理，若某学生账号在 ``students`` 里
**匹配不到任何行**，也保持 NULL。

方言安全
--------
DDL 用 ``op.batch_alter_table``（SQLite 需要借助 batch 模式重建表来加外键/索引，
MySQL 直接 ALTER）。回填用纯 SQL ``UPDATE ... JOIN`` 之外的**方言无关写法**：
先用 ``SELECT`` 取到「无歧义的 (user_id, student_id) 映射」，再用
``executemany`` 风格的参数化 ``UPDATE`` 逐行写回 —— 避免 MySQL ``UPDATE JOIN``
与 SQLite 语法差异。

幂等/可重跑
-----------
``upgrade()`` 开头检测 ``student_id`` 列是否已存在，存在则跳过整段（该项目迁移链
遵循「迁移链 = 模型 schema」，允许开发中反复重跑；参照 ``a4b6c8d0e2f4`` 的收敛风格）。
回填本身是幂等的：已填行不满足 ``student_id IS NULL`` 条件，重跑不会改动。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5e6f7a8b9d0'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEX_NAME = 'ix_users_student_id'
_FK_NAME = 'users_student_id_fk'


def _column_exists(conn, table: str, column: str) -> bool:
    """检测表中是否已存在某列（跨方言）。"""
    inspector = sa.inspect(conn)
    return any(c['name'] == column for c in inspector.get_columns(table))


def _index_exists(conn, table: str, index: str) -> bool:
    """检测表中是否已存在某索引（跨方言）。"""
    inspector = sa.inspect(conn)
    return any(ix['name'] == index for ix in inspector.get_indexes(table))


def _backfill(conn) -> tuple[int, int]:
    """按 (class_id, name) 回填 student_id。

    Returns:
        (filled, skipped_conflict)：成功回填行数、因歧义跳过行数。
    """
    # 1) 各 (class_id, name) 在 students 中对应的行数 —— 用于识别歧义键。
    conflict_keys = set()
    for row in conn.execute(sa.text(
        "SELECT class_id, name FROM students "
        "GROUP BY class_id, name HAVING COUNT(*) > 1"
    )):
        conflict_keys.add((row[0], row[1]))

    # 2) 取所有待回填的学生账号（student_id 为 NULL 且 class_id/name 齐全）。
    pending = conn.execute(sa.text(
        "SELECT id, class_id, name FROM users "
        "WHERE role = 'student' AND student_id IS NULL "
        "AND class_id IS NOT NULL AND name IS NOT NULL"
    )).fetchall()

    filled = 0
    skipped_conflict = 0
    updates: list[dict] = []
    for user_id, class_id, name in pending:
        if (class_id, name) in conflict_keys:
            skipped_conflict += 1
            continue
        sid = conn.execute(
            sa.text(
                "SELECT id FROM students WHERE class_id = :cid AND name = :nm LIMIT 1"
            ),
            {"cid": class_id, "nm": name},
        ).scalar()
        if sid is None:
            # 匹配不到任何档案（如账号已建、档案未建）—— 保持 NULL。
            continue
        updates.append({"uid": user_id, "sid": sid})
        filled += 1

    if updates:
        conn.execute(
            sa.text("UPDATE users SET student_id = :sid WHERE id = :uid"),
            updates,
        )
    return filled, skipped_conflict


def upgrade() -> None:
    """新增 users.student_id 外键列 + 索引，并回填历史学生账号。"""
    conn = op.get_bind()

    if _column_exists(conn, 'users', 'student_id'):
        # 已存在（重跑场景）：仍尝试回填 NULL 行，保证收敛。
        filled, skipped = _backfill(conn)
        print(f"[c5e6f7a8b9d0] student_id 列已存在，跳过 DDL；回填 {filled} 行 / 跳过 {skipped} 行（冲突）")
        return

    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('student_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            _FK_NAME, 'students', ['student_id'], ['id'], ondelete='SET NULL',
        )
        batch_op.create_index(_INDEX_NAME, ['student_id'], unique=False)

    filled, skipped = _backfill(conn)
    print(f"[c5e6f7a8b9d0] 回填 {filled} 行 / 跳过 {skipped} 行（冲突）")


def downgrade() -> None:
    """回滚：删除外键、索引与列。

    🔴 **顺序必须是先删外键、再删索引**：MySQL 不允许删除「被外键依赖的索引」
    （``DROP INDEX`` 会报 1553 "needed in a foreign key constraint"）。索引
    ``ix_users_student_id`` 同时支撑 ``users_student_id_fk``，故必须先
    ``drop_constraint`` 释放依赖，才能 ``drop_index``，最后 ``drop_column``。
    （对照 ``b1c2d3e4f5a6`` 用 ``drop_table`` 连带清索引的做法；此处是 ALTER，不能偷懒。）
    """
    conn = op.get_bind()
    if not _column_exists(conn, 'users', 'student_id'):
        return
    # 先删外键（MySQL 要求），再删索引，最后删列。
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint(_FK_NAME, type_='foreignkey')
    with op.batch_alter_table('users') as batch_op:
        if _index_exists(conn, 'users', _INDEX_NAME):
            batch_op.drop_index(_INDEX_NAME)
        batch_op.drop_column('student_id')
