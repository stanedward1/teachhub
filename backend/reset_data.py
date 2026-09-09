"""清空系统业务数据，仅保留「能让系统运行」的最小数据。

保留内容：
- 默认学校（****学校）1 所
- 平台超管 admin / 学校管理员 school_admin / 教师 teacher / teacher2 共 4 个账号

清空内容：
- 所有学生档案（students）及其账号（users.role='student'）
- 所有班级（classrooms）、科任关联（class_teachers）
- 作业链（work_comments -> excellent_works -> submission_comments -> submissions
           -> assignment_attachments -> assignments）
- 成绩/请假/考勤/表现/沟通/谈心/返校记录/评语/画像标签（student_id 引用表）
- 资源/试卷/座位/课程表/活动/工作日志/计划总结/周报/导入历史
- 第二所学校（第二职业技术学校）及其 teacher3、5 名学生
- 系统设置（settings）与操作日志（operation_logs）

用法：
    cd backend
    python reset_data.py

说明：脚本幂等，可重复执行；不重建表结构，不删除迁移历史。
"""

from app.database import SessionLocal
from app.models import (
    Activity,
    Assignment,
    AssignmentAttachment,
    Attendance,
    ClassPlan,
    ClassTeacher,
    Classroom,
    Communication,
    ExcellentWork,
    Exam,
    ImportHistory,
    Leave,
    OperationLog,
    Performance,
    Resource,
    ReturnRecord,
    Schedule,
    School,
    Score,
    Seat,
    Setting,
    Student,
    StudentBoardHistory,
    StudentComment,
    StudentProfileTag,
    Submission,
    SubmissionComment,
    Talk,
    TeacherPlan,
    User,
    WeeklyReport,
    WorkComment,
    WorkLog,
)


def _count(db, model):
    return db.query(model).count()


def reset():
    db = SessionLocal()
    try:
        before = {m.__tablename__: _count(db, m) for m in _ALL_MODELS}
        print("清理前数据量：")
        for t, c in before.items():
            print(f"  {t:25s} {c}")

        # ============ 1. 作业链（叶子 -> 根） ============
        db.query(WorkComment).delete(synchronize_session=False)
        db.query(ExcellentWork).delete(synchronize_session=False)
        db.query(SubmissionComment).delete(synchronize_session=False)
        db.query(Submission).delete(synchronize_session=False)
        db.query(AssignmentAttachment).delete(synchronize_session=False)
        db.query(Assignment).delete(synchronize_session=False)

        # ============ 2. student_id 直接引用的业务表 ============
        for model in (
            Score, Leave, Communication, Attendance, Performance,
            Talk, ReturnRecord, StudentComment, StudentProfileTag,
            StudentBoardHistory,
        ):
            db.query(model).delete(synchronize_session=False)

        # ============ 3. 其它独立业务表 ============
        for model in (
            Resource, Exam, Seat, Schedule, Activity,
            WorkLog, ClassPlan, TeacherPlan, WeeklyReport, ImportHistory,
        ):
            db.query(model).delete(synchronize_session=False)

        # ============ 4. 删除所有学生账号（users.class_id 外键指向 classrooms，须先删） ============
        db.query(User).filter(User.role == "student").delete(
            synchronize_session=False
        )

        # ============ 5. 学生档案 ============
        db.query(Student).delete(synchronize_session=False)

        # ============ 6. 班级与科任关联（须在删除教师账号前删除，因 classrooms.teacher_id 指向 users.id） ============
        db.query(ClassTeacher).delete(synchronize_session=False)
        db.query(Classroom).delete(synchronize_session=False)

        # ============ 7. 删除默认学校之外的其它学校及其账号（如 seed 生成的第二职业技术学校） ============
        # 默认学校以业务编码 XYZJ01 为准（比 name 字符串更可靠）。
        default_school = db.query(School).filter(School.code == "XYZJ01").first()
        keep_school_id = default_school.id if default_school else None
        # 其它学校（跨租户验证用）全部删除
        other_schools = (
            db.query(School).all()
            if keep_school_id is None
            else db.query(School).filter(School.id != keep_school_id).all()
        )
        other_school_ids = [s.id for s in other_schools]
        if other_school_ids:
            # 删除这些学校的教师/管理员账号
            db.query(User).filter(
                User.school_id.in_(other_school_ids),
            ).delete(synchronize_session=False)
            # 删除这些学校
            db.query(School).filter(School.id.in_(other_school_ids)).delete(
                synchronize_session=False
            )

        # ============ 8. 系统设置与操作日志 ============
        db.query(Setting).delete(synchronize_session=False)
        db.query(OperationLog).delete(synchronize_session=False)

        db.commit()

        # ============ 统计输出 ============
        print("\n清理后数据量：")
        for m in _ALL_MODELS:
            print(f"  {m.__tablename__:25s} {_count(db, m)}")
        print("\n保留账号：")
        for u in db.query(User).all():
            print(f"  [{u.role:12s}] {u.username}  (school_id={u.school_id})")
        print("\n清理完成，系统可正常登录并录入真实数据。")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


_ALL_MODELS = [
    User, School, Classroom, ClassTeacher, Student,
    Assignment, AssignmentAttachment, Submission, ExcellentWork,
    WorkComment, SubmissionComment,
    Score, Leave, Communication, Resource, Exam, Seat, Setting,
    ImportHistory, StudentProfileTag, WeeklyReport, StudentBoardHistory,
    Attendance, WorkLog, ClassPlan, TeacherPlan, Schedule, Activity,
    Talk, ReturnRecord, Performance, StudentComment, OperationLog,
]


if __name__ == "__main__":
    reset()
