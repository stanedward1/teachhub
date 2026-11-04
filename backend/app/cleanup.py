"""删除操作的级联清理辅助函数。

问题背景：删除学生账号（User）或学生档案（Student）时，若只删单条记录，
会残留大量孤儿数据：

- 学生账号（users）与档案（students）的**唯一锚点是 `users.student_id` 硬外键**，
  不是「班级 + 姓名」。软匹配只剩 `permissions.get_account_of_student` 内部一处，
  且只在归属唯一可判定时兜底（RBT-35 / RBT-65）—— **调用点不要自己写软匹配**，
  否则会 purge 掉同班同名同学的账号。
- 学生档案被 **14 张**业务表通过 `student_id` 引用：提交链的 `submissions` /
  `excellent_works` / `work_comments` / `submission_comments`（见 `purge_student_data`）
  + `_STUDENT_DATA_MODELS` 的 10 张。复核：
  `python -c "from app.cleanup import _STUDENT_DATA_MODELS as m; print(len(m) + 4)"` ⇒ 14
- 头像文件（uploads/avatars/*）不会被自动清理。

SQLite 默认不开启外键约束，因此这些孤儿数据不会立刻报错，但会引发后续
接口的数据不一致（甚至 500）。故删除学生时必须级联清理。
"""
import os

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
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

# 所有以 student_id 引用 students.id 的业务模型（无子表依赖，可平铺删除）。
# 注意：Submission 不在此列——它被 excellent_works / submission_comments
# 通过 submission_id 外键引用，需按「叶子 → 根」顺序单独级联处理。
_STUDENT_DATA_MODELS = [
    Score,
    Leave,
    Communication,
    Attendance,
    Performance,
    Talk,
    ReturnRecord,
    StudentComment,
    StudentProfileTag,
    StudentBoardHistory,
]

# ---- 删除账号时，指向 `users.id` 的引用分两类处理 ----
# 🔴 两类语义完全不同，所以名字必须不同（RDB-68）：早先把 `(School, "created_by")`
# 混进「统一 DELETE」的列表里，注释写的是「兜底」，实际是**删掉整所学校**（RBT-72）。
# 判断标准只有一句：这一行是「账号的产出」还是「账号参与过的独立实体」？
#   产出 ⇒ 删行；独立实体 ⇒ 只断引用（置 NULL），行留下。

# ① 只断开引用：目标是独立实体，账号只是负责人 / 创建人。
_LINK_ONLY_MODELS: list[tuple[type, str]] = [
    (Classroom, "teacher_id"),  # 班主任：班级必须保留，仅清 teacher_id
    (School, "created_by"),  # 学校创建人：学校必须保留，仅清 created_by
]

# ② 整行删除：目标是该账号的产出，账号没了就没有存在意义。
_PURGE_MODELS: list[tuple[type, str]] = [
    (WorkLog, "teacher_id"),
    (ClassPlan, "teacher_id"),
    (TeacherPlan, "teacher_id"),
    (Talk, "teacher_id"),
    (ImportHistory, "user_id"),
    (WeeklyReport, "created_by"),
    (StudentBoardHistory, "changed_by"),
]


def purge_student_data(db: Session, student_id: int) -> None:
    """级联删除某学生档案关联的全部业务数据（不 commit，由调用方统一提交）。

    依赖关系（箭头 = 外键引用方向，需反向删除）：
      work_comments -> excellent_works -> submissions
      submission_comments -> submissions
    因此删除该学生的 submissions 前，须先删引用它们的子表。
    """
    # 1) 该学生的所有提交（submissions）
    sub_ids = [
        r[0]
        for r in db.query(Submission.id)
        .filter(Submission.student_id == student_id)
        .all()
    ]
    if sub_ids:
        # 1.1 这些提交被评选的优秀作品（excellent_works）
        ew_ids = [
            r[0]
            for r in db.query(ExcellentWork.id)
            .filter(ExcellentWork.submission_id.in_(sub_ids))
            .all()
        ]
        if ew_ids:
            # 1.1.1 优秀作品下的评论（work_comments，叶子）
            db.query(WorkComment).filter(
                WorkComment.excellent_id.in_(ew_ids)
            ).delete(synchronize_session=False)
            # 1.1.2 优秀作品本身
            db.query(ExcellentWork).filter(
                ExcellentWork.id.in_(ew_ids)
            ).delete(synchronize_session=False)
        # 1.2 这些提交的点评（submission_comments）
        db.query(SubmissionComment).filter(
            SubmissionComment.submission_id.in_(sub_ids)
        ).delete(synchronize_session=False)
        # 1.3 提交本身
        db.query(Submission).filter(Submission.id.in_(sub_ids)).delete(
            synchronize_session=False
        )
    # 2) 其余以 student_id 直接引用的业务表（无子表依赖）
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

    因此删除账号前必须显式处理所有指向该 users.id 的引用，按**目标性质**分两组
    （对应模块级 `_LINK_ONLY_MODELS` / `_PURGE_MODELS`）：

    ① 只断引用、保留行（目标独立存在）：
    - 班级班主任（classrooms.teacher_id）：班级保留，置 NULL
    - 学校创建人（schools.created_by）：学校保留，置 NULL —— 删掉一位超管**不能连带
      删掉他建的整所学校**（RBT-72：SQLite 下留孤儿班级；MySQL 下 `classrooms.school_id`
      未声明 ondelete ⇒ RESTRICT ⇒ 该账号永远删不掉、接口 500）

    ② 整行删除（目标就是该账号的产出）：
    - 科任关联（class_teachers.teacher_id）
    - 教学/作业：assignments(created_by)、excellent_works(selected_by)、
      work_comments(user_id)、submission_comments(teacher_id)
    - 日志/计划：work_logs、class_plans、teacher_plans、talks(teacher_id)
    - 历史/报表：import_history(user_id)、weekly_reports(created_by)、
      student_board_history(changed_by)
    """
    # 1) 只断开引用：班级与学校都是独立实体，账号只是负责人 / 创建人 ⇒ 置 NULL
    for model, col in _LINK_ONLY_MODELS:
        db.query(model).filter(getattr(model, col) == user_id).update(
            {col: None}, synchronize_session=False
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
    # 挂在这些提交下的优秀作品 id（3.1 / 3.2 两段对同一 sub_ids 的查询逐字相同，
    # 只查一次共用）
    ew_by_sub = []
    if sub_ids:
        ew_by_sub = [
            r[0]
            for r in db.query(ExcellentWork.id)
            .filter(ExcellentWork.submission_id.in_(sub_ids))
            .all()
        ]

    # 3.1 最底层：work_comments（引用 excellent_works.id 或 users.id）
    #     先删「该用户发布的评论」+「挂在将被删除的 excellent_works 下的评论」
    excellent_ids_to_del = set(selected_excellent_ids)
    excellent_ids_to_del.update(ew_by_sub)
    wc_cond = WorkComment.user_id == user_id
    if excellent_ids_to_del:
        wc_cond = or_(wc_cond, WorkComment.excellent_id.in_(list(excellent_ids_to_del)))
    db.query(WorkComment).filter(wc_cond).delete(synchronize_session=False)

    # 3.2 excellent_works：删「该教师评选的」+「挂在将被删 submissions 下的」
    ew_ids = set(selected_excellent_ids)
    ew_ids.update(ew_by_sub)
    if ew_ids:
        db.query(ExcellentWork).filter(ExcellentWork.id.in_(list(ew_ids))).delete(
            synchronize_session=False
        )

    # 3.3 submission_comments：删「该教师点评的」+「挂在将被删 submissions 下的」
    sc_cond = SubmissionComment.teacher_id == user_id
    if sub_ids:
        sc_cond = or_(sc_cond, SubmissionComment.submission_id.in_(sub_ids))
    db.query(SubmissionComment).filter(sc_cond).delete(synchronize_session=False)

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

    # 4) 其余直接引用 users.id 且无子表依赖的业务表（整行删除，见 `_PURGE_MODELS`）
    for model, col in _PURGE_MODELS:
        db.query(model).filter(getattr(model, col) == user_id).delete(
            synchronize_session=False
        )


def delete_avatar_file(avatar_url: str | None) -> None:
    """删除头像文件（avatar 形如 /uploads/avatars/xxx.png）。

    基于 settings.AVATAR_DIR（由 UPLOAD_DIR 派生，默认 backend/uploads/avatars）解析存储位置，
    与 auth.py / students_service.py 实际写入的目录同源；文件不存在则静默跳过。
    """
    if not avatar_url or not avatar_url.startswith("/uploads/avatars/"):
        return
    # avatar 形如 /uploads/avatars/xxx.png，实际存储在 <AVATAR_DIR>/xxx.png
    full = os.path.join(settings.AVATAR_DIR, os.path.basename(avatar_url))
    try:
        if os.path.exists(full):
            os.remove(full)
    except OSError:
        # 头像文件清理失败不影响主流程（删除操作本身仍应成功）
        pass
