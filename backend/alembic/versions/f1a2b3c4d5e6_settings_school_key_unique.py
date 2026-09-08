"""settings 表：key 全局唯一 → (school_id, key) 校内唯一

Revision ID: f1a2b3c4d5e6
Revises: c9d8e7f6a5b4
Create Date: 2026-09-08 11:30:00

多租户下不同学校可设置同名配置项（如 current_grade），原 UNIQUE(key) 会导致冲突。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'c9d8e7f6a5b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite 不支持直接删除唯一约束，需重建表
        op.execute(
            """
            CREATE TABLE settings_new (
                id INTEGER NOT NULL PRIMARY KEY,
                school_id INTEGER,
                "key" VARCHAR(50) NOT NULL,
                value VARCHAR(255),
                CONSTRAINT uq_settings_school_key UNIQUE (school_id, "key")
            )
            """
        )
        op.execute(
            "INSERT INTO settings_new (id, school_id, key, value) "
            "SELECT id, school_id, key, value FROM settings"
        )
        op.execute("DROP TABLE settings")
        op.execute("ALTER TABLE settings_new RENAME TO settings")
        op.create_index(op.f("ix_settings_id"), "settings", ["id"], unique=False)
        op.create_index(op.f("ix_settings_school_id"), "settings", ["school_id"], unique=False)
        op.create_index(op.f("ix_settings_key"), "settings", ["key"], unique=False)
    else:
        # MySQL/PostgreSQL：删除旧的 key 唯一约束，新增 (school_id, key) 联合唯一
        op.drop_constraint("key", "settings", type_="unique")
        op.create_unique_constraint("uq_settings_school_key", "settings", ["school_id", "key"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.execute(
            """
            CREATE TABLE settings_old (
                id INTEGER NOT NULL PRIMARY KEY,
                school_id INTEGER,
                "key" VARCHAR(50) NOT NULL,
                value VARCHAR(255),
                CONSTRAINT uq_settings_key UNIQUE ("key")
            )
            """
        )
        op.execute(
            "INSERT INTO settings_old (id, school_id, key, value) "
            "SELECT id, school_id, key, value FROM settings"
        )
        op.execute("DROP TABLE settings")
        op.execute("ALTER TABLE settings_old RENAME TO settings")
        op.create_index(op.f("ix_settings_id"), "settings", ["id"], unique=False)
        op.create_index(op.f("ix_settings_school_id"), "settings", ["school_id"], unique=False)
        op.create_index(op.f("ix_settings_key"), "settings", ["key"], unique=False)
    else:
        op.drop_constraint("uq_settings_school_key", "settings", type_="unique")
        op.create_unique_constraint("key", "settings", ["key"])
