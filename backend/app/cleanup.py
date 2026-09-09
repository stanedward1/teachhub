"""删除操作的级联清理辅助函数。

问题背景：删除学生账号（User）或学生档案（Student）时，若只删单条记录，
会残留大量孤儿数据：
- 学生账号（users）与档案（students）通过「班级 + 姓名」关联，删一个不删另一个会不一致；
- 学生档案被 11 张业务表（scores/submissions/attendance/performances/...）通过 student_id 引用；
- 头像文件（uploads/avatars/*）不会被自动清理。

SQLite 默认不开启外键约束，因此这些孤儿数据不会立刻报错，但会引发后续
接口的数据不一致（甚至 500）。故删除学生时必须级联清理。
"""
import os

from sqlalchemy.orm import Session

from app.models import (
    Assignment,
    Attendance,
    ClassPlan,
    ClassTeacher,
    Classroom,
    Communication,
    ExcellentWork,
    ImportHistory,
    Leave,
    Performance,
    ReturnRecord,
    School,
    Score,
    StudentBoardHistory,
    StudentComment,
    StudentProfileTag,
    Submission,
    SubmissionComment,
    Talk,
    TeacherPlan,
    WeeklyReport,
    WorkComment,
    WorkLog,
)

# 所有以 student_id 引用 students.id 的业务模型（按删除顺序，无特殊依赖）
_STUDENT_DATA_MODELS = [
    Score,
    Leave,
    Communication,
    Submission,
    Attendance,
    Performance,
    Talk,
    ReturnRecord,
    StudentComment,
    StudentProfileTag,
    StudentBoardHistory,
]


def purge_student_data(db: Session, student_id: int) -> None:
    """级联删除某学生档案关联的全部业务数据（不 commit，由调用方统一提交）。"""
    for model in _STUDENT_DATA_MODELS:
        db.query(model).filter(model.student_id == student_id).delete(
            synchronize_session=False
        )


def purge_user_data(db: Session, user_id: int) -> None:
    """级联删除某账号（users）关联的全部引用数据（不 commit，由调用方统一提交）。

    问题背景：SQLite 默认不启用外键，删除账号时若只删 users 一行，
    残留在其他表的 user_id / teacher_id / created_by / changed_by / selected_by
    引用会成为孤儿数据；而 MySQL（InnoDB）默认强制外键约束，会直接拒绝删除
    并抛错（导致 DELETE /api/admin/users/{id} 返回 500）。

    因此删除账号前必须显式清理所有指向该 users.id 的业务记录：
    - 班级班主任（classrooms.teacher_id）与科任关联（class_teachers.teacher_id）
    - 教学/作业：assignments(created_by)、excellent_works(selected_by)、
      work_comments(user_id)、submission_comments(teacher_id)
    - 日志/计划：work_logs、class_plans、teacher_plans、talks(teacher_id)
    - 历史/报表：import_history(user_id)、weekly_reports(created_by)、
      student_board_history(changed_by)
    - 学校创建人（schools.created_by，仅超管场景，删除平台超管时兜底）
    """
    # 1) 班主任：清除 classroom 上指向该用户的 teacher_id（置空即可，班级保留）
    db.query(Classroom).filter(Classroom.teacher_id == user_id).update(
        {"teacher_id": None}, synchronize_session=False
    )
    # 2) 科任关联：直接删除
    db.query(ClassTeacher).filter(ClassTeacher.teacher_id == user_id).delete(
        synchronize_session=False
    )
    # 3) 其余以 user_id / teacher_id / created_by / selected_by / changed_by 引用的业务表
    _USER_DATA_MODELS = [
        # (模型, 引用列名)
        (Assignment, "created_by"),
        (ExcellentWork, "selected_by"),
        (WorkComment, "user_id"),
        (SubmissionComment, "teacher_id"),
        (WorkLog, "teacher_id"),
        (ClassPlan, "teacher_id"),
        (TeacherPlan, "teacher_id"),
        (Talk, "teacher_id"),
        (ImportHistory, "user_id"),
        (WeeklyReport, "created_by"),
        (StudentBoardHistory, "changed_by"),
        (School, "created_by"),
    ]
    for model, col in _USER_DATA_MODELS:
        db.query(model).filter(getattr(model, col) == user_id).delete(
            synchronize_session=False
        )


def delete_avatar_file(avatar_url: str | None) -> None:
    """删除头像文件（avatar 形如 /uploads/avatars/xxx.png）。

    基于项目根目录（backend/ 上一级）解析相对路径；文件不存在则静默跳过。
    """
    if not avatar_url or not avatar_url.startswith("/uploads/avatars/"):
        return
    # avatar 路径形如 /uploads/avatars/xxx.png，实际存储在 <backend>/uploads/avatars/xxx.png
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    full = os.path.join(base, "uploads", "avatars", os.path.basename(avatar_url))
    try:
        if os.path.exists(full):
            os.remove(full)
    except OSError:
        # 头像文件清理失败不影响主流程（删除操作本身仍应成功）
        pass
