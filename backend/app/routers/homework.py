from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit import batch_user_map, audit
from app.database import get_db
from app.deps import get_current_user, require_student, require_teacher
from app.models import (
    Assignment,
    AssignmentAttachment,
    Classroom,
    ExcellentWork,
    Student,
    Submission,
    SubmissionComment,
    User,
    WorkComment,
)
from app.permissions import (
    ensure_class_operable,
    ensure_student_operable,
    get_teacher_class_ids,
    is_teacher_class_owner,
)
from app.utils import to_dict

router = APIRouter(prefix="/api/homework", tags=["作业提交平台"])


def _check_student_access(assignment: Assignment, user: User):
    if user.role == "student" and assignment.class_id != user.class_id:
        raise HTTPException(status_code=403, detail="无权访问该任务")


def _check_teacher_assignment_access(db: Session, user: User, assignment: Assignment):
    """教师只能访问自己负责班级的作业/提交，管理员不受限。"""
    if assignment is None:
        return
    if user.role == "teacher" and not is_teacher_class_owner(db, user.id, assignment.class_id):
        raise HTTPException(status_code=403, detail="无权访问其他班级的任务")


def _ensure_submission_operable(db: Session, submission: Submission):
    """校验提交对应的学生是否可被教师操作（退学/毕业限制）。"""
    stu_user = db.get(User, submission.student_id)
    assignment = db.get(Assignment, submission.assignment_id)
    class_id = assignment.class_id if assignment else None
    if stu_user and class_id:
        student = (
            db.query(Student)
            .filter(Student.class_id == class_id, Student.name == stu_user.name)
            .first()
        )
        if student:
            ensure_student_operable(db, student.id)


def _attachments_out(a: Assignment) -> list:
    """把作业附件转成对外结构 [{id, filename, filepath}]。"""
    return [
        {"id": att.id, "filename": att.filename, "filepath": att.filepath}
        for att in a.attachments
    ]


def _sync_attachments(a: Assignment, attachments) -> None:
    """同步作业附件（传入 [{filename, filepath}, ...]，整体替换旧附件）。"""
    a.attachments.clear()
    for att in attachments or []:
        if isinstance(att, dict) and att.get("filename") and att.get("filepath"):
            a.attachments.append(
                AssignmentAttachment(filename=att["filename"], filepath=att["filepath"])
            )


# ---------------- 作业任务 ----------------
@router.get("/assignments")
def list_assignments(
    class_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Assignment)
    if user.role == "student":
        q = q.filter(Assignment.class_id == user.class_id)
    elif user.role == "teacher":
        # 教师只看自己负责班级的作业
        q = q.filter(Assignment.class_id.in_(get_teacher_class_ids(db, user.id)))
    elif class_id:
        q = q.filter(Assignment.class_id == class_id)

    rows = q.order_by(Assignment.created_at.desc(), Assignment.id.desc()).all()
    items = []
    for a in rows:
        d = to_dict(a)
        cls = db.get(Classroom, a.class_id)
        creator = db.get(User, a.created_by)
        d["class_name"] = cls.name if cls else None
        d["creator_name"] = creator.name if creator else None
        d["attachment_count"] = len(a.attachments)
        d["submission_count"] = (
            db.query(Submission).filter(Submission.assignment_id == a.id).count()
        )
        if user.role == "student":
            d["my_submitted"] = (
                db.query(Submission)
                .filter(Submission.assignment_id == a.id, Submission.student_id == user.id)
                .count()
                > 0
            )
        items.append(d)
    return {"items": items, "total": len(items)}


@router.get("/assignments/{assignment_id}")
def get_assignment(
    assignment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="任务不存在")
    _check_student_access(a, user)
    _check_teacher_assignment_access(db, user, a)
    d = to_dict(a)
    cls = db.get(Classroom, a.class_id)
    creator = db.get(User, a.created_by)
    d["class_name"] = cls.name if cls else None
    d["creator_name"] = creator.name if creator else None
    d["attachments"] = _attachments_out(a)
    return d


@router.post("/assignments")
def create_assignment(payload: dict, user: User = Depends(require_teacher), db: Session = Depends(get_db)):
    title = (payload.get("title") or "").strip()
    content = (payload.get("content") or "").strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="标题和内容不能为空")
    class_id = payload.get("class_id")
    if not class_id or not db.get(Classroom, class_id):
        raise HTTPException(status_code=400, detail="请选择下发班级")
    # 毕业限制：毕业班级不可再布置作业
    ensure_class_operable(db, class_id)
    # 教师只能给自己负责的班级布置作业
    if user.role != "admin" and not is_teacher_class_owner(db, user.id, class_id):
        raise HTTPException(status_code=403, detail="只能给自己负责的班级布置作业")

    a = Assignment(
        title=title,
        description=payload.get("description", ""),
        content=content,
        deadline=payload.get("deadline"),
        created_by=user.id,
        class_id=class_id,
        short_name=payload.get("short_name") or title,
    )
    _sync_attachments(a, payload.get("attachments"))
    db.add(a)
    audit(db, user, "create_assignment", target=f"布置作业", class_id=class_id)
    db.commit()
    db.refresh(a)
    d = to_dict(a)
    d["attachments"] = _attachments_out(a)
    return d


@router.put("/assignments/{assignment_id}")
def update_assignment(
    assignment_id: int, payload: dict, user: User = Depends(require_teacher), db: Session = Depends(get_db)
):
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="任务不存在")
    if a.created_by != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="只能编辑自己创建的任务")
    for field in ("title", "description", "content", "deadline", "short_name"):
        if field in payload and payload[field] is not None:
            setattr(a, field, payload[field])
    if "attachments" in payload:
        _sync_attachments(a, payload["attachments"])
    if payload.get("class_id") and db.get(Classroom, payload["class_id"]):
        # 毕业限制：不可将作业转移到已毕业班级
        ensure_class_operable(db, payload["class_id"])
        a.class_id = payload["class_id"]
    audit(db, user, "update_assignment", target=f"作业#{assignment_id}", class_id=a.class_id)
    db.commit()
    db.refresh(a)
    d = to_dict(a)
    d["attachments"] = _attachments_out(a)
    return d


@router.delete("/assignments/{assignment_id}")
def delete_assignment(
    assignment_id: int, user: User = Depends(require_teacher), db: Session = Depends(get_db)
):
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="任务不存在")
    if a.created_by != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="只能删除自己创建的任务")
    db.delete(a)
    audit(db, user, "delete_assignment", target=f"作业#{assignment_id}", class_id=a.class_id)
    db.commit()
    return {"ok": True}


# ---------------- 作业提交 ----------------
@router.get("/assignments/{assignment_id}/submissions")
def list_submissions(
    assignment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="任务不存在")
    _check_student_access(a, user)
    _check_teacher_assignment_access(db, user, a)
    q = db.query(Submission).filter(Submission.assignment_id == assignment_id)
    if user.role == "student":
        q = q.filter(Submission.student_id == user.id)
    rows = q.order_by(Submission.created_at.desc(), Submission.id.desc()).all()
    # 批量查询，避免 N+1
    uid_map = batch_user_map(db, [s.student_id for s in rows])
    sid_list = [s.id for s in rows]
    excellent_ids = {
        e.submission_id
        for e in db.query(ExcellentWork.submission_id)
        .filter(ExcellentWork.submission_id.in_(sid_list))
        .all()
    }
    items = []
    for s in rows:
        d = to_dict(s)
        info = uid_map.get(s.student_id)
        d["student_name"] = info["name"] if info else None
        d["student_avatar"] = info["avatar"] if info else None
        d["is_excellent"] = s.id in excellent_ids
        items.append(d)
    return {"items": items, "total": len(items)}


@router.get("/submissions/{submission_id}")
def get_submission(
    submission_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取提交详情（含完整内容 + 教师点评列表）。"""
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(status_code=404, detail="提交不存在")
    a = db.get(Assignment, s.assignment_id)
    _check_student_access(a, user)
    _check_teacher_assignment_access(db, user, a)
    if user.role == "student" and s.student_id != user.id:
        raise HTTPException(status_code=403, detail="无权查看该提交")

    d = to_dict(s)
    stu = db.get(User, s.student_id)
    d["student_name"] = stu.name if stu else None
    d["student_avatar"] = stu.avatar if stu else None
    d["is_excellent"] = (
        db.query(ExcellentWork).filter(ExcellentWork.submission_id == submission_id).first() is not None
    )
    comments = (
        db.query(SubmissionComment)
        .filter(SubmissionComment.submission_id == submission_id)
        .order_by(SubmissionComment.id.asc())
        .all()
    )
    comment_items = []
    for c in comments:
        cd = to_dict(c)
        t = db.get(User, c.teacher_id)
        cd["teacher_name"] = t.name if t else None
        comment_items.append(cd)
    d["comments"] = comment_items
    return d


@router.post("/submissions/{submission_id}/comments")
def add_submission_comment(
    submission_id: int,
    payload: dict,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师对提交添加点评（含可选评分）。"""
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(status_code=404, detail="提交不存在")
    # 教师只能点评自己班级的提交
    _check_teacher_assignment_access(db, user, db.get(Assignment, s.assignment_id))
    # 退学/毕业限制
    _ensure_submission_operable(db, s)
    content = (payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="点评内容不能为空")
    score = payload.get("score")
    if score is not None:
        score = int(score)
        if not 0 <= score <= 100:
            raise HTTPException(status_code=400, detail="评分需在 0-100 之间")
    c = SubmissionComment(
        submission_id=submission_id,
        teacher_id=user.id,
        content=content,
        score=score,
    )
    db.add(c)
    stu = db.get(User, s.student_id)
    stu_name = stu.name if stu else ""
    audit(db, user, "add_submission_comment", target=f"点评-{stu_name}", student_id=s.student_id)
    db.commit()
    db.refresh(c)
    cd = to_dict(c)
    cd["teacher_name"] = user.name
    return cd


@router.delete("/submissions/{submission_id}/comments/{comment_id}")
def delete_submission_comment(
    submission_id: int,
    comment_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """删除点评（仅点评者本人或管理员）。"""
    c = db.get(SubmissionComment, comment_id)
    if not c or c.submission_id != submission_id:
        raise HTTPException(status_code=404, detail="点评不存在")
    if user.role != "admin" and c.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="无权删除该点评")
    # 退学/毕业限制 + 教师只能操作自己班级的提交
    s = db.get(Submission, submission_id)
    if s:
        _check_teacher_assignment_access(db, user, db.get(Assignment, s.assignment_id))
        _ensure_submission_operable(db, s)
    db.delete(c)
    stu = db.get(User, s.student_id) if s else None
    stu_name = stu.name if stu else ""
    audit(db, user, "delete_submission_comment", target=f"删除点评-{stu_name}", student_id=s.student_id)
    db.commit()
    return {"ok": True}


@router.post("/assignments/{assignment_id}/submissions")
def submit(
    assignment_id: int,
    payload: dict,
    user: User = Depends(require_student),
    db: Session = Depends(get_db),
):
    a = db.get(Assignment, assignment_id)
    if not a:
        raise HTTPException(status_code=404, detail="任务不存在")
    _check_student_access(a, user)
    content = (payload.get("content") or "").strip()
    filepath = payload.get("filepath")
    filename = payload.get("filename")
    if not content and not filepath:
        raise HTTPException(status_code=400, detail="请填写作业内容或上传文件")

    existing = (
        db.query(Submission)
        .filter(Submission.assignment_id == assignment_id, Submission.student_id == user.id)
        .first()
    )
    if existing:
        existing.content = content
        existing.filepath = filepath or existing.filepath
        existing.filename = filename or existing.filename
        db.commit()
        db.refresh(existing)
        return to_dict(existing)

    s = Submission(
        assignment_id=assignment_id,
        student_id=user.id,
        content=content,
        filename=filename,
        filepath=filepath,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return to_dict(s)


@router.get("/my-submissions")
def my_submissions(user: User = Depends(require_student), db: Session = Depends(get_db)):
    rows = (
        db.query(Submission)
        .filter(Submission.student_id == user.id)
        .order_by(Submission.created_at.desc())
        .all()
    )
    items = []
    for s in rows:
        d = to_dict(s)
        a = db.get(Assignment, s.assignment_id)
        d["assignment_title"] = a.title if a else None
        d["is_excellent"] = (
            db.query(ExcellentWork).filter(ExcellentWork.submission_id == s.id).count() > 0
        )
        items.append(d)
    return {"items": items, "total": len(items)}


# ---------------- 优秀作品 ----------------
@router.post("/submissions/{submission_id}/excellent")
def mark_excellent(
    submission_id: int,
    payload: dict,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(status_code=404, detail="提交不存在")
    # 教师只能评自己班级的提交为优秀
    _check_teacher_assignment_access(db, user, db.get(Assignment, s.assignment_id))
    # 退学/毕业限制
    _ensure_submission_operable(db, s)
    existing = db.query(ExcellentWork).filter(ExcellentWork.submission_id == submission_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="该作品已入选优秀")
    e = ExcellentWork(submission_id=submission_id, selected_by=user.id, note=payload.get("note", ""))
    db.add(e)
    audit(db, user, "mark_excellent", target=f"优秀-提交#{submission_id}", student_id=s.student_id)
    db.commit()
    db.refresh(e)
    return to_dict(e)


@router.delete("/submissions/{submission_id}/excellent")
def unmark_excellent(
    submission_id: int, user: User = Depends(require_teacher), db: Session = Depends(get_db)
):
    e = db.query(ExcellentWork).filter(ExcellentWork.submission_id == submission_id).first()
    if e:
        # 教师只能操作自己班级的提交 + 退学/毕业限制
        s = db.get(Submission, submission_id)
        if s:
            _check_teacher_assignment_access(db, user, db.get(Assignment, s.assignment_id))
            _ensure_submission_operable(db, s)
        db.delete(e)
        audit(db, user, "unmark_excellent", target=f"取消优秀-提交#{submission_id}", student_id=s.student_id if s else None)
        db.commit()
    return {"ok": True}


@router.get("/excellent")
def list_excellent(
    page: int = 1,
    page_size: int = 12,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(ExcellentWork)
    if user.role == "student":
        # 学生仅查看本班作业的优秀作品
        q = (
            q.join(Submission, ExcellentWork.submission_id == Submission.id)
            .join(Assignment, Submission.assignment_id == Assignment.id)
            .filter(Assignment.class_id == user.class_id)
        )
    elif user.role == "teacher":
        # 教师仅查看自己班级的优秀作品
        q = (
            q.join(Submission, ExcellentWork.submission_id == Submission.id)
            .join(Assignment, Submission.assignment_id == Assignment.id)
            .filter(Assignment.class_id.in_(get_teacher_class_ids(db, user.id)))
        )
    total = q.count()
    rows = (
        q.order_by(ExcellentWork.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    if not rows:
        return {"items": [], "total": total}

    # 批量查询所有关联对象，避免 N+1
    sub_ids = [e.submission_id for e in rows]
    subs = {s.id: s for s in db.query(Submission).filter(Submission.id.in_(sub_ids)).all()}
    assign_ids = {s.assignment_id for s in subs.values() if s.assignment_id}
    assigns = {a.id: a for a in db.query(Assignment).filter(Assignment.id.in_(assign_ids)).all()} if assign_ids else {}
    stu_ids = {s.student_id for s in subs.values() if s.student_id}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(stu_ids)).all()} if stu_ids else {}
    cls_ids = {a.class_id for a in assigns.values() if a.class_id}
    classes = {c.id: c for c in db.query(Classroom).filter(Classroom.id.in_(cls_ids)).all()} if cls_ids else {}
    comment_counts = dict(
        db.query(WorkComment.excellent_id, func.count(WorkComment.id))
        .filter(WorkComment.excellent_id.in_([e.id for e in rows]))
        .group_by(WorkComment.excellent_id)
        .all()
    )

    items = []
    for e in rows:
        s = subs.get(e.submission_id)
        if not s:
            continue
        a = assigns.get(s.assignment_id)
        stu = users.get(s.student_id)
        cls = classes.get(a.class_id) if a else None
        items.append(
            {
                "id": e.id,
                "note": e.note,
                "created_at": e.created_at,
                "submission": to_dict(s),
                "assignment_title": a.title if a else None,
                "assignment_id": a.id if a else None,
                "student_name": stu.name if stu else None,
                "student_avatar": stu.avatar if stu else None,
                "class_name": cls.name if cls else None,
                "comment_count": comment_counts.get(e.id, 0),
            }
        )
    return {"items": items, "total": total}


@router.get("/excellent/{excellent_id}")
def get_excellent(
    excellent_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    e = db.get(ExcellentWork, excellent_id)
    if not e:
        raise HTTPException(status_code=404, detail="作品不存在")
    s = db.get(Submission, e.submission_id)
    a = db.get(Assignment, s.assignment_id) if s else None
    stu = db.get(User, s.student_id) if s else None
    cls = db.get(Classroom, a.class_id) if a else None
    comments = (
        db.query(WorkComment)
        .filter(WorkComment.excellent_id == excellent_id)
        .order_by(WorkComment.created_at.asc())
        .all()
    )
    comment_items = []
    for c in comments:
        cd = to_dict(c)
        cu = db.get(User, c.user_id)
        cd["user_name"] = cu.name if cu else None
        cd["user_avatar"] = cu.avatar if cu else None
        comment_items.append(cd)
    return {
        "id": e.id,
        "note": e.note,
        "created_at": e.created_at,
        "submission": to_dict(s),
        "assignment_title": a.title if a else None,
        "assignment_id": a.id if a else None,
        "student_name": stu.name if stu else None,
        "student_avatar": stu.avatar if stu else None,
        "class_name": cls.name if cls else None,
        "comments": comment_items,
    }


@router.post("/excellent/{excellent_id}/comments")
def add_comment(
    excellent_id: int,
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not db.get(ExcellentWork, excellent_id):
        raise HTTPException(status_code=404, detail="作品不存在")
    content = (payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="评论内容不能为空")
    c = WorkComment(excellent_id=excellent_id, user_id=user.id, content=content)
    db.add(c)
    db.commit()
    db.refresh(c)
    d = to_dict(c)
    d["user_name"] = user.name
    d["user_avatar"] = user.avatar
    return d
