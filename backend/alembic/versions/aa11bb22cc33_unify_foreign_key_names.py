"""统一外键约束命名 + 补建缺失的 school_id 外键。

Revision ID: aa11bb22cc33
Revises: b7c8d9e0f1a2
Create Date: 2026-10-10

背景：
1. 项目 Base 无 naming_convention，历史 ForeignKey() 均未写 name=，MySQL 自动生成
   _ibfk_N；另有 2 个手工命名风格不一（submissions_student_id_fk /
   users_student_id_fk 后缀风格）。本迁移把全部 55 个外键统一为
   fk_<表>_<列> 前缀风格（对齐 fk_users_class_id 既有先例）。
2. 多租户迁移 c9d8e7f6a5b4 加 school_id 时只 add_column + create_index，
   从未 create_foreign_key，导致 28 个「模型声明 ForeignKey(schools.id) 但
   DB 无约束」的 schema gap。本迁移一并补建（已校验零孤儿数据）。

SQLite 方言跳过：SQLite 不支持 ALTER TABLE ... DROP FOREIGN KEY，且测试库
外键约束本就关闭，无需此迁移。
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'aa11bb22cc33'
down_revision: Union[str, Sequence[str], None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return

    # 1) 改名：DROP 旧外键 + ADD 新外键（统一 fk_ 前缀）
    op.execute("ALTER TABLE activities DROP FOREIGN KEY activities_ibfk_1")
    op.create_foreign_key(
        "fk_activities_class_id", "activities", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE ai_companion_conversations DROP FOREIGN KEY ai_companion_conversations_ibfk_1")
    op.create_foreign_key(
        "fk_ai_companion_conversations_school_id", "ai_companion_conversations", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE ai_companion_conversations DROP FOREIGN KEY ai_companion_conversations_ibfk_2")
    op.create_foreign_key(
        "fk_ai_companion_conversations_student_id", "ai_companion_conversations", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE ai_companion_conversations DROP FOREIGN KEY ai_companion_conversations_ibfk_3")
    op.create_foreign_key(
        "fk_ai_companion_conversations_assignment_id", "ai_companion_conversations", "assignments", ['assignment_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE ai_companion_messages DROP FOREIGN KEY ai_companion_messages_ibfk_1")
    op.create_foreign_key(
        "fk_ai_companion_messages_conversation_id", "ai_companion_messages", "ai_companion_conversations", ['conversation_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE ai_companion_messages DROP FOREIGN KEY ai_companion_messages_ibfk_2")
    op.create_foreign_key(
        "fk_ai_companion_messages_school_id", "ai_companion_messages", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE ai_companion_usage_daily_student DROP FOREIGN KEY ai_companion_usage_daily_student_ibfk_1")
    op.create_foreign_key(
        "fk_ai_companion_usage_daily_student_student_id", "ai_companion_usage_daily_student", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE ai_companion_usage_daily_student DROP FOREIGN KEY ai_companion_usage_daily_student_ibfk_2")
    op.create_foreign_key(
        "fk_ai_companion_usage_daily_student_school_id", "ai_companion_usage_daily_student", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE ai_credentials DROP FOREIGN KEY ai_credentials_ibfk_1")
    op.create_foreign_key(
        "fk_ai_credentials_updated_by", "ai_credentials", "users", ['updated_by'], ['id'],
    )
    op.execute("ALTER TABLE ai_grading_results DROP FOREIGN KEY ai_grading_results_ibfk_1")
    op.create_foreign_key(
        "fk_ai_grading_results_submission_id", "ai_grading_results", "submissions", ['submission_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE ai_grading_results DROP FOREIGN KEY ai_grading_results_ibfk_2")
    op.create_foreign_key(
        "fk_ai_grading_results_school_id", "ai_grading_results", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE ai_usage_daily_companion_school DROP FOREIGN KEY ai_usage_daily_companion_school_ibfk_1")
    op.create_foreign_key(
        "fk_ai_usage_daily_companion_school_school_id", "ai_usage_daily_companion_school", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE ai_usage_daily_school DROP FOREIGN KEY ai_usage_daily_school_ibfk_1")
    op.create_foreign_key(
        "fk_ai_usage_daily_school_school_id", "ai_usage_daily_school", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE assignment_attachments DROP FOREIGN KEY assignment_attachments_ibfk_1")
    op.create_foreign_key(
        "fk_assignment_attachments_assignment_id", "assignment_attachments", "assignments", ['assignment_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE assignments DROP FOREIGN KEY assignments_ibfk_1")
    op.create_foreign_key(
        "fk_assignments_class_id", "assignments", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE assignments DROP FOREIGN KEY assignments_ibfk_2")
    op.create_foreign_key(
        "fk_assignments_created_by", "assignments", "users", ['created_by'], ['id'],
    )
    op.execute("ALTER TABLE attendance DROP FOREIGN KEY attendance_ibfk_1")
    op.create_foreign_key(
        "fk_attendance_class_id", "attendance", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE attendance DROP FOREIGN KEY attendance_ibfk_2")
    op.create_foreign_key(
        "fk_attendance_student_id", "attendance", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE class_plans DROP FOREIGN KEY class_plans_ibfk_1")
    op.create_foreign_key(
        "fk_class_plans_teacher_id", "class_plans", "users", ['teacher_id'], ['id'],
    )
    op.execute("ALTER TABLE class_teachers DROP FOREIGN KEY class_teachers_ibfk_1")
    op.create_foreign_key(
        "fk_class_teachers_class_id", "class_teachers", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE class_teachers DROP FOREIGN KEY class_teachers_ibfk_2")
    op.create_foreign_key(
        "fk_class_teachers_teacher_id", "class_teachers", "users", ['teacher_id'], ['id'],
    )
    op.execute("ALTER TABLE classrooms DROP FOREIGN KEY classrooms_ibfk_1")
    op.create_foreign_key(
        "fk_classrooms_school_id", "classrooms", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE classrooms DROP FOREIGN KEY classrooms_ibfk_2")
    op.create_foreign_key(
        "fk_classrooms_teacher_id", "classrooms", "users", ['teacher_id'], ['id'],
    )
    op.execute("ALTER TABLE communications DROP FOREIGN KEY communications_ibfk_1")
    op.create_foreign_key(
        "fk_communications_student_id", "communications", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE excellent_works DROP FOREIGN KEY excellent_works_ibfk_1")
    op.create_foreign_key(
        "fk_excellent_works_selected_by", "excellent_works", "users", ['selected_by'], ['id'],
    )
    op.execute("ALTER TABLE excellent_works DROP FOREIGN KEY excellent_works_ibfk_2")
    op.create_foreign_key(
        "fk_excellent_works_submission_id", "excellent_works", "submissions", ['submission_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE import_history DROP FOREIGN KEY import_history_ibfk_1")
    op.create_foreign_key(
        "fk_import_history_user_id", "import_history", "users", ['user_id'], ['id'],
    )
    op.execute("ALTER TABLE leaves DROP FOREIGN KEY leaves_ibfk_1")
    op.create_foreign_key(
        "fk_leaves_student_id", "leaves", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE performances DROP FOREIGN KEY performances_ibfk_1")
    op.create_foreign_key(
        "fk_performances_student_id", "performances", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE refresh_tokens DROP FOREIGN KEY refresh_tokens_ibfk_1")
    op.create_foreign_key(
        "fk_refresh_tokens_user_id", "refresh_tokens", "users", ['user_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE refresh_tokens DROP FOREIGN KEY refresh_tokens_ibfk_2")
    op.create_foreign_key(
        "fk_refresh_tokens_school_id", "refresh_tokens", "schools", ['school_id'], ['id'], ondelete="SET NULL",
    )
    op.execute("ALTER TABLE return_records DROP FOREIGN KEY return_records_ibfk_1")
    op.create_foreign_key(
        "fk_return_records_student_id", "return_records", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE schedules DROP FOREIGN KEY schedules_ibfk_1")
    op.create_foreign_key(
        "fk_schedules_class_id", "schedules", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE scores DROP FOREIGN KEY scores_ibfk_1")
    op.create_foreign_key(
        "fk_scores_student_id", "scores", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE seats DROP FOREIGN KEY seats_ibfk_1")
    op.create_foreign_key(
        "fk_seats_class_id", "seats", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE student_board_history DROP FOREIGN KEY student_board_history_ibfk_1")
    op.create_foreign_key(
        "fk_student_board_history_student_id", "student_board_history", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE student_board_history DROP FOREIGN KEY student_board_history_ibfk_2")
    op.create_foreign_key(
        "fk_student_board_history_changed_by", "student_board_history", "users", ['changed_by'], ['id'],
    )
    op.execute("ALTER TABLE student_comments DROP FOREIGN KEY student_comments_ibfk_1")
    op.create_foreign_key(
        "fk_student_comments_student_id", "student_comments", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE student_profile_tags DROP FOREIGN KEY student_profile_tags_ibfk_1")
    op.create_foreign_key(
        "fk_student_profile_tags_student_id", "student_profile_tags", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE students DROP FOREIGN KEY students_ibfk_1")
    op.create_foreign_key(
        "fk_students_class_id", "students", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE students DROP FOREIGN KEY students_ibfk_2")
    op.create_foreign_key(
        "fk_students_school_id", "students", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE submission_comments DROP FOREIGN KEY submission_comments_ibfk_1")
    op.create_foreign_key(
        "fk_submission_comments_submission_id", "submission_comments", "submissions", ['submission_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE submission_comments DROP FOREIGN KEY submission_comments_ibfk_2")
    op.create_foreign_key(
        "fk_submission_comments_teacher_id", "submission_comments", "users", ['teacher_id'], ['id'],
    )
    op.execute("ALTER TABLE submissions DROP FOREIGN KEY submissions_ibfk_1")
    op.create_foreign_key(
        "fk_submissions_assignment_id", "submissions", "assignments", ['assignment_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE submissions DROP FOREIGN KEY submissions_student_id_fk")
    op.create_foreign_key(
        "fk_submissions_student_id", "submissions", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE talks DROP FOREIGN KEY talks_ibfk_1")
    op.create_foreign_key(
        "fk_talks_student_id", "talks", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE talks DROP FOREIGN KEY talks_ibfk_2")
    op.create_foreign_key(
        "fk_talks_teacher_id", "talks", "users", ['teacher_id'], ['id'],
    )
    op.execute("ALTER TABLE teacher_plans DROP FOREIGN KEY teacher_plans_ibfk_1")
    op.create_foreign_key(
        "fk_teacher_plans_teacher_id", "teacher_plans", "users", ['teacher_id'], ['id'],
    )
    op.execute("ALTER TABLE users DROP FOREIGN KEY users_student_id_fk")
    op.create_foreign_key(
        "fk_users_student_id", "users", "students", ['student_id'], ['id'], ondelete="SET NULL",
    )
    op.execute("ALTER TABLE weekly_reports DROP FOREIGN KEY weekly_reports_ibfk_1")
    op.create_foreign_key(
        "fk_weekly_reports_class_id", "weekly_reports", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE weekly_reports DROP FOREIGN KEY weekly_reports_ibfk_2")
    op.create_foreign_key(
        "fk_weekly_reports_created_by", "weekly_reports", "users", ['created_by'], ['id'],
    )
    op.execute("ALTER TABLE work_comments DROP FOREIGN KEY work_comments_ibfk_1")
    op.create_foreign_key(
        "fk_work_comments_excellent_id", "work_comments", "excellent_works", ['excellent_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE work_comments DROP FOREIGN KEY work_comments_ibfk_2")
    op.create_foreign_key(
        "fk_work_comments_user_id", "work_comments", "users", ['user_id'], ['id'],
    )
    op.execute("ALTER TABLE work_logs DROP FOREIGN KEY work_logs_ibfk_1")
    op.create_foreign_key(
        "fk_work_logs_teacher_id", "work_logs", "users", ['teacher_id'], ['id'],
    )

    # 2) 补建缺失的 school_id 外键（模型有、DB 无）
    op.create_foreign_key(
        "fk_activities_school_id", "activities", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_assignments_school_id", "assignments", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_attendance_school_id", "attendance", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_class_plans_school_id", "class_plans", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_communications_school_id", "communications", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_exams_school_id", "exams", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_excellent_works_school_id", "excellent_works", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_import_history_school_id", "import_history", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_leaves_school_id", "leaves", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_performances_school_id", "performances", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_resources_school_id", "resources", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_return_records_school_id", "return_records", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_schedules_school_id", "schedules", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_schools_created_by", "schools", "users", ['created_by'], ['id'],
    )
    op.create_foreign_key(
        "fk_scores_school_id", "scores", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_seats_school_id", "seats", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_settings_school_id", "settings", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_student_board_history_school_id", "student_board_history", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_student_comments_school_id", "student_comments", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_student_profile_tags_school_id", "student_profile_tags", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_submission_comments_school_id", "submission_comments", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_submissions_school_id", "submissions", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_talks_school_id", "talks", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_teacher_plans_school_id", "teacher_plans", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_users_school_id", "users", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_weekly_reports_school_id", "weekly_reports", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_work_comments_school_id", "work_comments", "schools", ['school_id'], ['id'],
    )
    op.create_foreign_key(
        "fk_work_logs_school_id", "work_logs", "schools", ['school_id'], ['id'],
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return

    # 2) 删补建的外键（逆序）
    op.execute("ALTER TABLE work_logs DROP FOREIGN KEY fk_work_logs_school_id")
    op.execute("ALTER TABLE work_comments DROP FOREIGN KEY fk_work_comments_school_id")
    op.execute("ALTER TABLE weekly_reports DROP FOREIGN KEY fk_weekly_reports_school_id")
    op.execute("ALTER TABLE users DROP FOREIGN KEY fk_users_school_id")
    op.execute("ALTER TABLE teacher_plans DROP FOREIGN KEY fk_teacher_plans_school_id")
    op.execute("ALTER TABLE talks DROP FOREIGN KEY fk_talks_school_id")
    op.execute("ALTER TABLE submissions DROP FOREIGN KEY fk_submissions_school_id")
    op.execute("ALTER TABLE submission_comments DROP FOREIGN KEY fk_submission_comments_school_id")
    op.execute("ALTER TABLE student_profile_tags DROP FOREIGN KEY fk_student_profile_tags_school_id")
    op.execute("ALTER TABLE student_comments DROP FOREIGN KEY fk_student_comments_school_id")
    op.execute("ALTER TABLE student_board_history DROP FOREIGN KEY fk_student_board_history_school_id")
    op.execute("ALTER TABLE settings DROP FOREIGN KEY fk_settings_school_id")
    op.execute("ALTER TABLE seats DROP FOREIGN KEY fk_seats_school_id")
    op.execute("ALTER TABLE scores DROP FOREIGN KEY fk_scores_school_id")
    op.execute("ALTER TABLE schools DROP FOREIGN KEY fk_schools_created_by")
    op.execute("ALTER TABLE schedules DROP FOREIGN KEY fk_schedules_school_id")
    op.execute("ALTER TABLE return_records DROP FOREIGN KEY fk_return_records_school_id")
    op.execute("ALTER TABLE resources DROP FOREIGN KEY fk_resources_school_id")
    op.execute("ALTER TABLE performances DROP FOREIGN KEY fk_performances_school_id")
    op.execute("ALTER TABLE leaves DROP FOREIGN KEY fk_leaves_school_id")
    op.execute("ALTER TABLE import_history DROP FOREIGN KEY fk_import_history_school_id")
    op.execute("ALTER TABLE excellent_works DROP FOREIGN KEY fk_excellent_works_school_id")
    op.execute("ALTER TABLE exams DROP FOREIGN KEY fk_exams_school_id")
    op.execute("ALTER TABLE communications DROP FOREIGN KEY fk_communications_school_id")
    op.execute("ALTER TABLE class_plans DROP FOREIGN KEY fk_class_plans_school_id")
    op.execute("ALTER TABLE attendance DROP FOREIGN KEY fk_attendance_school_id")
    op.execute("ALTER TABLE assignments DROP FOREIGN KEY fk_assignments_school_id")
    op.execute("ALTER TABLE activities DROP FOREIGN KEY fk_activities_school_id")

    # 1) 回滚改名（逆序）：DROP 新外键 + ADD 旧外键
    op.execute("ALTER TABLE work_logs DROP FOREIGN KEY fk_work_logs_teacher_id")
    op.create_foreign_key(
        "work_logs_ibfk_1", "work_logs", "users", ['teacher_id'], ['id'],
    )
    op.execute("ALTER TABLE work_comments DROP FOREIGN KEY fk_work_comments_user_id")
    op.create_foreign_key(
        "work_comments_ibfk_2", "work_comments", "users", ['user_id'], ['id'],
    )
    op.execute("ALTER TABLE work_comments DROP FOREIGN KEY fk_work_comments_excellent_id")
    op.create_foreign_key(
        "work_comments_ibfk_1", "work_comments", "excellent_works", ['excellent_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE weekly_reports DROP FOREIGN KEY fk_weekly_reports_created_by")
    op.create_foreign_key(
        "weekly_reports_ibfk_2", "weekly_reports", "users", ['created_by'], ['id'],
    )
    op.execute("ALTER TABLE weekly_reports DROP FOREIGN KEY fk_weekly_reports_class_id")
    op.create_foreign_key(
        "weekly_reports_ibfk_1", "weekly_reports", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE users DROP FOREIGN KEY fk_users_student_id")
    op.create_foreign_key(
        "users_student_id_fk", "users", "students", ['student_id'], ['id'], ondelete="SET NULL",
    )
    op.execute("ALTER TABLE teacher_plans DROP FOREIGN KEY fk_teacher_plans_teacher_id")
    op.create_foreign_key(
        "teacher_plans_ibfk_1", "teacher_plans", "users", ['teacher_id'], ['id'],
    )
    op.execute("ALTER TABLE talks DROP FOREIGN KEY fk_talks_teacher_id")
    op.create_foreign_key(
        "talks_ibfk_2", "talks", "users", ['teacher_id'], ['id'],
    )
    op.execute("ALTER TABLE talks DROP FOREIGN KEY fk_talks_student_id")
    op.create_foreign_key(
        "talks_ibfk_1", "talks", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE submissions DROP FOREIGN KEY fk_submissions_student_id")
    op.create_foreign_key(
        "submissions_student_id_fk", "submissions", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE submissions DROP FOREIGN KEY fk_submissions_assignment_id")
    op.create_foreign_key(
        "submissions_ibfk_1", "submissions", "assignments", ['assignment_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE submission_comments DROP FOREIGN KEY fk_submission_comments_teacher_id")
    op.create_foreign_key(
        "submission_comments_ibfk_2", "submission_comments", "users", ['teacher_id'], ['id'],
    )
    op.execute("ALTER TABLE submission_comments DROP FOREIGN KEY fk_submission_comments_submission_id")
    op.create_foreign_key(
        "submission_comments_ibfk_1", "submission_comments", "submissions", ['submission_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE students DROP FOREIGN KEY fk_students_school_id")
    op.create_foreign_key(
        "students_ibfk_2", "students", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE students DROP FOREIGN KEY fk_students_class_id")
    op.create_foreign_key(
        "students_ibfk_1", "students", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE student_profile_tags DROP FOREIGN KEY fk_student_profile_tags_student_id")
    op.create_foreign_key(
        "student_profile_tags_ibfk_1", "student_profile_tags", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE student_comments DROP FOREIGN KEY fk_student_comments_student_id")
    op.create_foreign_key(
        "student_comments_ibfk_1", "student_comments", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE student_board_history DROP FOREIGN KEY fk_student_board_history_changed_by")
    op.create_foreign_key(
        "student_board_history_ibfk_2", "student_board_history", "users", ['changed_by'], ['id'],
    )
    op.execute("ALTER TABLE student_board_history DROP FOREIGN KEY fk_student_board_history_student_id")
    op.create_foreign_key(
        "student_board_history_ibfk_1", "student_board_history", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE seats DROP FOREIGN KEY fk_seats_class_id")
    op.create_foreign_key(
        "seats_ibfk_1", "seats", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE scores DROP FOREIGN KEY fk_scores_student_id")
    op.create_foreign_key(
        "scores_ibfk_1", "scores", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE schedules DROP FOREIGN KEY fk_schedules_class_id")
    op.create_foreign_key(
        "schedules_ibfk_1", "schedules", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE return_records DROP FOREIGN KEY fk_return_records_student_id")
    op.create_foreign_key(
        "return_records_ibfk_1", "return_records", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE refresh_tokens DROP FOREIGN KEY fk_refresh_tokens_school_id")
    op.create_foreign_key(
        "refresh_tokens_ibfk_2", "refresh_tokens", "schools", ['school_id'], ['id'], ondelete="SET NULL",
    )
    op.execute("ALTER TABLE refresh_tokens DROP FOREIGN KEY fk_refresh_tokens_user_id")
    op.create_foreign_key(
        "refresh_tokens_ibfk_1", "refresh_tokens", "users", ['user_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE performances DROP FOREIGN KEY fk_performances_student_id")
    op.create_foreign_key(
        "performances_ibfk_1", "performances", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE leaves DROP FOREIGN KEY fk_leaves_student_id")
    op.create_foreign_key(
        "leaves_ibfk_1", "leaves", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE import_history DROP FOREIGN KEY fk_import_history_user_id")
    op.create_foreign_key(
        "import_history_ibfk_1", "import_history", "users", ['user_id'], ['id'],
    )
    op.execute("ALTER TABLE excellent_works DROP FOREIGN KEY fk_excellent_works_submission_id")
    op.create_foreign_key(
        "excellent_works_ibfk_2", "excellent_works", "submissions", ['submission_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE excellent_works DROP FOREIGN KEY fk_excellent_works_selected_by")
    op.create_foreign_key(
        "excellent_works_ibfk_1", "excellent_works", "users", ['selected_by'], ['id'],
    )
    op.execute("ALTER TABLE communications DROP FOREIGN KEY fk_communications_student_id")
    op.create_foreign_key(
        "communications_ibfk_1", "communications", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE classrooms DROP FOREIGN KEY fk_classrooms_teacher_id")
    op.create_foreign_key(
        "classrooms_ibfk_2", "classrooms", "users", ['teacher_id'], ['id'],
    )
    op.execute("ALTER TABLE classrooms DROP FOREIGN KEY fk_classrooms_school_id")
    op.create_foreign_key(
        "classrooms_ibfk_1", "classrooms", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE class_teachers DROP FOREIGN KEY fk_class_teachers_teacher_id")
    op.create_foreign_key(
        "class_teachers_ibfk_2", "class_teachers", "users", ['teacher_id'], ['id'],
    )
    op.execute("ALTER TABLE class_teachers DROP FOREIGN KEY fk_class_teachers_class_id")
    op.create_foreign_key(
        "class_teachers_ibfk_1", "class_teachers", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE class_plans DROP FOREIGN KEY fk_class_plans_teacher_id")
    op.create_foreign_key(
        "class_plans_ibfk_1", "class_plans", "users", ['teacher_id'], ['id'],
    )
    op.execute("ALTER TABLE attendance DROP FOREIGN KEY fk_attendance_student_id")
    op.create_foreign_key(
        "attendance_ibfk_2", "attendance", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE attendance DROP FOREIGN KEY fk_attendance_class_id")
    op.create_foreign_key(
        "attendance_ibfk_1", "attendance", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE assignments DROP FOREIGN KEY fk_assignments_created_by")
    op.create_foreign_key(
        "assignments_ibfk_2", "assignments", "users", ['created_by'], ['id'],
    )
    op.execute("ALTER TABLE assignments DROP FOREIGN KEY fk_assignments_class_id")
    op.create_foreign_key(
        "assignments_ibfk_1", "assignments", "classrooms", ['class_id'], ['id'],
    )
    op.execute("ALTER TABLE assignment_attachments DROP FOREIGN KEY fk_assignment_attachments_assignment_id")
    op.create_foreign_key(
        "assignment_attachments_ibfk_1", "assignment_attachments", "assignments", ['assignment_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE ai_usage_daily_school DROP FOREIGN KEY fk_ai_usage_daily_school_school_id")
    op.create_foreign_key(
        "ai_usage_daily_school_ibfk_1", "ai_usage_daily_school", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE ai_usage_daily_companion_school DROP FOREIGN KEY fk_ai_usage_daily_companion_school_school_id")
    op.create_foreign_key(
        "ai_usage_daily_companion_school_ibfk_1", "ai_usage_daily_companion_school", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE ai_grading_results DROP FOREIGN KEY fk_ai_grading_results_school_id")
    op.create_foreign_key(
        "ai_grading_results_ibfk_2", "ai_grading_results", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE ai_grading_results DROP FOREIGN KEY fk_ai_grading_results_submission_id")
    op.create_foreign_key(
        "ai_grading_results_ibfk_1", "ai_grading_results", "submissions", ['submission_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE ai_credentials DROP FOREIGN KEY fk_ai_credentials_updated_by")
    op.create_foreign_key(
        "ai_credentials_ibfk_1", "ai_credentials", "users", ['updated_by'], ['id'],
    )
    op.execute("ALTER TABLE ai_companion_usage_daily_student DROP FOREIGN KEY fk_ai_companion_usage_daily_student_school_id")
    op.create_foreign_key(
        "ai_companion_usage_daily_student_ibfk_2", "ai_companion_usage_daily_student", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE ai_companion_usage_daily_student DROP FOREIGN KEY fk_ai_companion_usage_daily_student_student_id")
    op.create_foreign_key(
        "ai_companion_usage_daily_student_ibfk_1", "ai_companion_usage_daily_student", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE ai_companion_messages DROP FOREIGN KEY fk_ai_companion_messages_school_id")
    op.create_foreign_key(
        "ai_companion_messages_ibfk_2", "ai_companion_messages", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE ai_companion_messages DROP FOREIGN KEY fk_ai_companion_messages_conversation_id")
    op.create_foreign_key(
        "ai_companion_messages_ibfk_1", "ai_companion_messages", "ai_companion_conversations", ['conversation_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE ai_companion_conversations DROP FOREIGN KEY fk_ai_companion_conversations_assignment_id")
    op.create_foreign_key(
        "ai_companion_conversations_ibfk_3", "ai_companion_conversations", "assignments", ['assignment_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE ai_companion_conversations DROP FOREIGN KEY fk_ai_companion_conversations_student_id")
    op.create_foreign_key(
        "ai_companion_conversations_ibfk_2", "ai_companion_conversations", "students", ['student_id'], ['id'], ondelete="CASCADE",
    )
    op.execute("ALTER TABLE ai_companion_conversations DROP FOREIGN KEY fk_ai_companion_conversations_school_id")
    op.create_foreign_key(
        "ai_companion_conversations_ibfk_1", "ai_companion_conversations", "schools", ['school_id'], ['id'],
    )
    op.execute("ALTER TABLE activities DROP FOREIGN KEY fk_activities_class_id")
    op.create_foreign_key(
        "activities_ibfk_1", "activities", "classrooms", ['class_id'], ['id'],
    )
