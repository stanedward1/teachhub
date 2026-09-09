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
    AssignmentAttachment,
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

    # 3) 作业链级联清理（按「叶子 → 根」拓扑倒序删除，否则 MySQL 外键约束报错）
    #    依赖关系（箭头 = 外键引用方向，需反向删除）：
    #      work_comments -> excellent_works -> submissions -> assignments
    #      submission_comments -> submissions
    #      assignment_attachments -> assignments
    #      excellent_works.selected_by -> users（教师评选他人提交）
    #      work_comments.user_id -> users（用户评论）
    #      submission_comments.teacher_id -> users（教师点评）
    assignment_ids = [
        r[0]
        for r in db.query(Assignment.id)
        .filter(Assignment.created_by == user_id)
        .all()
    ]
    # 该教师评选的优秀作品（可能是他人作业下的提交）
    selected_excellent_ids = [
        r[0]
        for r in db.query(ExcellentWork.id)
        .filter(ExcellentWork.selected_by == user_id)
        .all()
    ]
    # 该教师作业下的所有提交
    sub_ids = []
    if assignment_ids:
        sub_ids = [
            r[0]
            for r in db.query(Submission.id)
            .filter(Submission.assignment_id.in_(assignment_ids))
            .all()
        ]

    # 3.1 最底层：work_comments（引用 excellent_works.id 或 users.id）
    #     先删「该用户发布的评论」+「挂在将被删除的 excellent_works 下的评论」
    wc_q = db.query(WorkComment).filter(WorkComment.user_id == user_id)
    if selected_excellent_ids or sub_ids:
        excellent_ids_to_del = set(selected_excellent_ids)
        # 该教师作业的 submissions 若被评选，对应的 excellent_works 也要删
        if sub_ids:
            ew_by_sub = [
                r[0]
                for r in db.query(ExcellentWork.id)
                .filter(ExcellentWork.submission_id.in_(sub_ids))
                .all()
            ]
            excellent_ids_to_del.update(ew_by_sub)
        if excellent_ids_to_del:
            wc_q = wc_q | db.query(WorkComment).filter(
                WorkComment.excellent_id.in_(list(excellent_ids_to_del))
            )
    wc_q.delete(synchronize_session=False)

    # 3.2 excellent_works：删「该教师评选的」+「挂在将被删 submissions 下的」
    ew_q = None
    if selected_excellent_ids:
        ew_q = db.query(ExcellentWork).filter(
            ExcellentWork.id.in_(selected_excellent_ids)
        )
    if sub_ids:
        q2 = db.query(ExcellentWork).filter(
            ExcellentWork.submission_id.in_(sub_ids)
        )
        ew_q = q2 if ew_q is None else ew_q.union(q2)
    if ew_q is not None:
        # union 结果需用子查询删除
        ids = [r[0] for r in ew_q.all()]
        if ids:
            db.query(ExcellentWork).filter(ExcellentWork.id.in_(ids)).delete(
                synchronize_session=False
            )

    # 3.3 submission_comments：删「该教师点评的」+「挂在将被删 submissions 下的」
    sc_q = db.query(SubmissionComment).filter(
        SubmissionComment.teacher_id == user_id
    )
    if sub_ids:
        sc_q = sc_q | db.query(SubmissionComment).filter(
            SubmissionComment.submission_id.in_(sub_ids)
        )
    sc_q.delete(synchronize_session=False)

    # 3.4 submissions（该教师作业下的提交）
    if sub_ids:
        db.query(Submission).filter(Submission.id.in_(sub_ids)).delete(
            synchronize_session=False
        )

    # 3.5 assignment_attachments + assignments
    if assignment_ids:
        db.query(AssignmentAttachment).filter(
            AssignmentAttachment.assignment_id.in_(assignment_ids)
        ).delete(synchronize_session=False)
        db.query(Assignment).filter(Assignment.id.in_(assignment_ids)).delete(
            synchronize_session=False
        )

    # 4) 其余直接引用 users.id 且无子表依赖的业务表
    _USER_DATA_MODELS = [
        # (模型, 引用列名)
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
