"""日期字段 String -> Date 类型统一；删除 students.avatar 冗余列

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-08 13:20:00

背景：
1. 8 个业务日期字段以字符串存储（work_logs.date、return_records.return_date、
   students.birth_date、leaves.start_date/end_date、weekly_reports.week_start/week_end、
   attendance.date），改为标准 Date 类型。
2. 头像统一存于 users.avatar（两个上传接口都写 users.avatar），students.avatar
   为从未写入的死列，予以删除。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 各表需要重建的索引：(索引名, 列, 是否唯一)
_INDEXES = {
    "work_logs": [
        ("ix_work_logs_id", ["id"], False),
        ("ix_work_logs_school_id", ["school_id"], False),
    ],
    "return_records": [
        ("ix_return_records_id", ["id"], False),
        ("ix_return_records_student_id", ["student_id"], False),
        ("ix_return_records_school_id", ["school_id"], False),
    ],
    "students": [
        ("ix_students_id", ["id"], False),
        ("ix_students_student_no", ["student_no"], True),
    ],
    "leaves": [
        ("ix_leaves_id", ["id"], False),
        ("ix_leaves_student_id", ["student_id"], False),
        ("ix_leaves_school_id", ["school_id"], False),
    ],
    "weekly_reports": [
        ("ix_weekly_reports_id", ["id"], False),
        ("ix_weekly_reports_class_id", ["class_id"], False),
        ("ix_weekly_reports_school_id", ["school_id"], False),
    ],
    "attendance": [
        ("ix_attendance_id", ["id"], False),
        ("ix_attendance_class_id", ["class_id"], False),
        ("ix_attendance_student_id", ["student_id"], False),
        ("ix_attendance_school_id", ["school_id"], False),
        ("ix_attendance_date", ["date"], False),
    ],
}


def _rebuild_sqlite(op, table: str, new_ddl: str, insert_cols: str, select_sql: str) -> None:
    """SQLite 重建表：CREATE new → 拷贝数据 → DROP old → RENAME → 重建索引。"""
    op.execute(new_ddl)
    op.execute(f"INSERT INTO {table}_new ({insert_cols}) SELECT {select_sql} FROM {table}")
    op.execute(f"DROP TABLE {table}")
    op.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
    for name, cols, unique in _INDEXES[table]:
        op.create_index(op.f(name), table, cols, unique=unique)


def _upgrade_sqlite() -> None:
    """SQLite 主路径：逐表重建，日期列 '' -> NULL，students 删除 avatar。"""
    _rebuild_sqlite(
        op, "work_logs",
        """CREATE TABLE work_logs_new (
            id INTEGER NOT NULL PRIMARY KEY,
            teacher_id INTEGER NOT NULL,
            date DATE,
            content TEXT,
            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
            updated_at DATETIME,
            school_id INTEGER,
            FOREIGN KEY(teacher_id) REFERENCES users (id)
        )""",
        "id, teacher_id, date, content, created_at, updated_at, school_id",
        "id, teacher_id, NULLIF(TRIM(date), ''), content, created_at, updated_at, school_id",
    )

    _rebuild_sqlite(
        op, "return_records",
        """CREATE TABLE return_records_new (
            id INTEGER NOT NULL PRIMARY KEY,
            student_id INTEGER NOT NULL,
            return_date DATE,
            reason VARCHAR(255),
            note TEXT,
            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
            school_id INTEGER,
            FOREIGN KEY(student_id) REFERENCES students (id)
        )""",
        "id, student_id, return_date, reason, note, created_at, school_id",
        "id, student_id, NULLIF(TRIM(return_date), ''), reason, note, created_at, school_id",
    )

    _rebuild_sqlite(
        op, "students",
        """CREATE TABLE students_new (
            id INTEGER NOT NULL PRIMARY KEY,
            school_id INTEGER,
            class_id INTEGER,
            name VARCHAR(50) NOT NULL,
            gender VARCHAR(10),
            birth_date DATE,
            student_no VARCHAR(50) NOT NULL,
            major VARCHAR(100),
            parent_name VARCHAR(50),
            parent_phone VARCHAR(20),
            student_type VARCHAR(20),
            status VARCHAR(20),
            is_dropped_out BOOLEAN DEFAULT '0' NOT NULL,
            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
            updated_at DATETIME,
            FOREIGN KEY(school_id) REFERENCES schools (id),
            FOREIGN KEY(class_id) REFERENCES classrooms (id)
        )""",
        "id, school_id, class_id, name, gender, birth_date, student_no, major, parent_name, parent_phone, student_type, status, is_dropped_out, created_at, updated_at",
        "id, school_id, class_id, name, gender, NULLIF(TRIM(birth_date), ''), student_no, major, parent_name, parent_phone, student_type, status, is_dropped_out, created_at, updated_at",
    )

    _rebuild_sqlite(
        op, "leaves",
        """CREATE TABLE leaves_new (
            id INTEGER NOT NULL PRIMARY KEY,
            student_id INTEGER NOT NULL,
            reason VARCHAR(255),
            start_date DATE,
            end_date DATE,
            status VARCHAR(20),
            image VARCHAR(500),
            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
            school_id INTEGER,
            FOREIGN KEY(student_id) REFERENCES students (id)
        )""",
        "id, student_id, reason, start_date, end_date, status, image, created_at, school_id",
        "id, student_id, reason, NULLIF(TRIM(start_date), ''), NULLIF(TRIM(end_date), ''), status, image, created_at, school_id",
    )

    _rebuild_sqlite(
        op, "weekly_reports",
        """CREATE TABLE weekly_reports_new (
            id INTEGER NOT NULL PRIMARY KEY,
            class_id INTEGER NOT NULL,
            title VARCHAR(200) NOT NULL,
            week_start DATE,
            week_end DATE,
            content TEXT,
            data_snapshot TEXT,
            created_by INTEGER,
            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
            updated_at DATETIME,
            school_id INTEGER,
            FOREIGN KEY(class_id) REFERENCES classrooms (id),
            FOREIGN KEY(created_by) REFERENCES users (id)
        )""",
        "id, class_id, title, week_start, week_end, content, data_snapshot, created_by, created_at, updated_at, school_id",
        "id, class_id, title, NULLIF(TRIM(week_start), ''), NULLIF(TRIM(week_end), ''), content, data_snapshot, created_by, created_at, updated_at, school_id",
    )

    _rebuild_sqlite(
        op, "attendance",
        """CREATE TABLE attendance_new (
            id INTEGER NOT NULL PRIMARY KEY,
            class_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            date DATE NOT NULL,
            status VARCHAR(20),
            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
            updated_at DATETIME,
            school_id INTEGER,
            FOREIGN KEY(class_id) REFERENCES classrooms (id),
            FOREIGN KEY(student_id) REFERENCES students (id),
            CONSTRAINT uq_attendance_student_date UNIQUE (class_id, student_id, date)
        )""",
        "id, class_id, student_id, date, status, created_at, updated_at, school_id",
        "id, class_id, student_id, NULLIF(TRIM(date), ''), status, created_at, updated_at, school_id",
    )


def _upgrade_other() -> None:
    """MySQL/PostgreSQL：直接 ALTER 列类型 + 删列 + 空串转 NULL。"""
    date_columns = [
        ("work_logs", "date", sa.String(20)),
        ("return_records", "return_date", sa.String(20)),
        ("students", "birth_date", sa.String(50)),
        ("leaves", "start_date", sa.String(20)),
        ("leaves", "end_date", sa.String(20)),
        ("weekly_reports", "week_start", sa.String(20)),
        ("weekly_reports", "week_end", sa.String(20)),
        ("attendance", "date", sa.String(20)),
    ]
    for table, col, existing_type in date_columns:
        op.execute(f"UPDATE {table} SET {col} = NULL WHERE {col} = ''")
        op.alter_column(table, col, existing_type=existing_type, type_=sa.Date(), existing_nullable=True)
    op.drop_column("students", "avatar")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _upgrade_sqlite()
    else:
        _upgrade_other()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # 回滚：日期列还原为字符串、students 加回 avatar 列（同样需重建表）
        _rebuild_sqlite(
            op, "work_logs",
            """CREATE TABLE work_logs_new (
                id INTEGER NOT NULL PRIMARY KEY,
                teacher_id INTEGER NOT NULL,
                date VARCHAR(20),
                content TEXT,
                created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
                updated_at DATETIME,
                school_id INTEGER,
                FOREIGN KEY(teacher_id) REFERENCES users (id)
            )""",
            "id, teacher_id, date, content, created_at, updated_at, school_id",
            "id, teacher_id, date, content, created_at, updated_at, school_id",
        )
        _rebuild_sqlite(
            op, "return_records",
            """CREATE TABLE return_records_new (
                id INTEGER NOT NULL PRIMARY KEY,
                student_id INTEGER NOT NULL,
                return_date VARCHAR(20),
                reason VARCHAR(255),
                note TEXT,
                created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
                school_id INTEGER,
                FOREIGN KEY(student_id) REFERENCES students (id)
            )""",
            "id, student_id, return_date, reason, note, created_at, school_id",
            "id, student_id, return_date, reason, note, created_at, school_id",
        )
        _rebuild_sqlite(
            op, "students",
            """CREATE TABLE students_new (
                id INTEGER NOT NULL PRIMARY KEY,
                school_id INTEGER,
                class_id INTEGER,
                name VARCHAR(50) NOT NULL,
                gender VARCHAR(10),
                birth_date VARCHAR(50),
                student_no VARCHAR(50) NOT NULL,
                major VARCHAR(100),
                parent_name VARCHAR(50),
                parent_phone VARCHAR(20),
                student_type VARCHAR(20),
                avatar VARCHAR(255),
                status VARCHAR(20),
                is_dropped_out BOOLEAN DEFAULT '0' NOT NULL,
                created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
                updated_at DATETIME,
                FOREIGN KEY(school_id) REFERENCES schools (id),
                FOREIGN KEY(class_id) REFERENCES classrooms (id)
            )""",
            "id, school_id, class_id, name, gender, birth_date, student_no, major, parent_name, parent_phone, student_type, avatar, status, is_dropped_out, created_at, updated_at",
            "id, school_id, class_id, name, gender, birth_date, student_no, major, parent_name, parent_phone, student_type, NULL, status, is_dropped_out, created_at, updated_at",
        )
        _rebuild_sqlite(
            op, "leaves",
            """CREATE TABLE leaves_new (
                id INTEGER NOT NULL PRIMARY KEY,
                student_id INTEGER NOT NULL,
                reason VARCHAR(255),
                start_date VARCHAR(20),
                end_date VARCHAR(20),
                status VARCHAR(20),
                image VARCHAR(500),
                created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
                school_id INTEGER,
                FOREIGN KEY(student_id) REFERENCES students (id)
            )""",
            "id, student_id, reason, start_date, end_date, status, image, created_at, school_id",
            "id, student_id, reason, start_date, end_date, status, image, created_at, school_id",
        )
        _rebuild_sqlite(
            op, "weekly_reports",
            """CREATE TABLE weekly_reports_new (
                id INTEGER NOT NULL PRIMARY KEY,
                class_id INTEGER NOT NULL,
                title VARCHAR(200) NOT NULL,
                week_start VARCHAR(20),
                week_end VARCHAR(20),
                content TEXT,
                data_snapshot TEXT,
                created_by INTEGER,
                created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
                updated_at DATETIME,
                school_id INTEGER,
                FOREIGN KEY(class_id) REFERENCES classrooms (id),
                FOREIGN KEY(created_by) REFERENCES users (id)
            )""",
            "id, class_id, title, week_start, week_end, content, data_snapshot, created_by, created_at, updated_at, school_id",
            "id, class_id, title, week_start, week_end, content, data_snapshot, created_by, created_at, updated_at, school_id",
        )
        _rebuild_sqlite(
            op, "attendance",
            """CREATE TABLE attendance_new (
                id INTEGER NOT NULL PRIMARY KEY,
                class_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                date VARCHAR(20) NOT NULL,
                status VARCHAR(20),
                created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
                updated_at DATETIME,
                school_id INTEGER,
                FOREIGN KEY(class_id) REFERENCES classrooms (id),
                FOREIGN KEY(student_id) REFERENCES students (id),
                CONSTRAINT uq_attendance_student_date UNIQUE (class_id, student_id, date)
            )""",
            "id, class_id, student_id, date, status, created_at, updated_at, school_id",
            "id, class_id, student_id, date, status, created_at, updated_at, school_id",
        )
    else:
        for table, col, existing_type in [
            ("work_logs", "date", sa.String(20)),
            ("return_records", "return_date", sa.String(20)),
            ("students", "birth_date", sa.String(50)),
            ("leaves", "start_date", sa.String(20)),
            ("leaves", "end_date", sa.String(20)),
            ("weekly_reports", "week_start", sa.String(20)),
            ("weekly_reports", "week_end", sa.String(20)),
            ("attendance", "date", sa.String(20)),
        ]:
            op.alter_column(table, col, existing_type=sa.Date(), type_=existing_type, existing_nullable=True)
        op.add_column("students", sa.Column("avatar", sa.String(255), nullable=True))
