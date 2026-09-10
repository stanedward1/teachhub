"""移动端专用轻量接口。

面向班主任/管理员在手机端的「学生速查」场景：
- 列表精简字段、默认排除退学学生，降低移动端流量；
- 画像概览一次返回五维雷达 + 成绩/积分/表现等关键摘要，避免多次请求。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.config import BASE_POINTS
from app.models import (
    ExcellentWork,
    Leave,
    Performance,
    Score,
    Student,
    StudentProfileTag,
    Submission,
    User,
)
from app.permissions import filter_students_by_teacher, is_any_admin, is_student_in_teacher_classes
from app.routers.students import _student_out, _students_out
from app.utils import clamp_score

router = APIRouter(prefix="/api", tags=["移动端"])


def _light_student(d: dict) -> dict:
    """从 _student_out 的完整字典中抽取移动端所需精简字段。"""
    return {
        "id": d["id"],
        "name": d["name"],
        "student_no": d["student_no"],
        "gender": d["gender"],
        "class_name": d["class_name"],
        "avatar": d["avatar"],
        "student_type": d["student_type"],
        "is_dropped_out": d["is_dropped_out"],
    }


@router.get("/mobile/students")
def mobile_students(
    class_id: int | None = None,
    keyword: str = "",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """移动端学生速查列表（精简字段，默认仅返回在籍学生）。"""
    is_admin = is_any_admin(user)
    q = filter_students_by_teacher(db, user.id, is_admin)
    q = q.filter(Student.is_dropped_out.is_(False))
    if class_id:
        q = q.filter(Student.class_id == class_id)
    if keyword:
        q = q.filter(
            Student.name.contains(keyword) | Student.student_no.contains(keyword)
        )
    rows = q.order_by(Student.id).limit(200).all()
    items = [_light_student(d) for d in _students_out(db, rows)]
    return {"items": items, "total": len(items)}


@router.get("/mobile/students/{student_id}/overview")
def mobile_student_overview(
    student_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """移动端学生画像概览：五维雷达 + 成绩/积分/表现等关键摘要。"""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
        raise HTTPException(status_code=403, detail="无权查看该学生画像")

    # 成绩
    scores = db.query(Score).filter(Score.student_id == student_id).all()
    avg = round(sum(s.score for s in scores) / len(scores), 1) if scores else 0
    score_summary = {
        "total": len(scores),
        "avg": avg,
        "max": max((s.score for s in scores), default=0),
        "min": min((s.score for s in scores), default=0),
        "recent": [
            {"subject": s.subject, "score": s.score, "exam": s.exam_name or "", "date": str(s.created_at)[:10]}
            for s in sorted(scores, key=lambda x: x.created_at, reverse=True)[:10]
        ],
    }

    # 表现 + 积分统计（一次查询派生两套口径；响应结构冻结）
    performances = db.query(Performance).filter(Performance.student_id == student_id).all()
    sorted_perfs = sorted(performances, key=lambda x: x.created_at, reverse=True)
    point_delta = sum((p.points or 0) for p in performances)
    point_summary = {
        "total": BASE_POINTS + point_delta,
        "positive": sum(v for v in ((p.points or 0) for p in performances) if v > 0),
        "negative": sum(v for v in ((p.points or 0) for p in performances) if v < 0),
        "count": len(performances),
        "recent": [
            {"points": p.points or 0, "reason": p.content or "", "date": str(p.created_at)[:10]}
            for p in sorted_perfs[:10]
        ],
    }
    performance_summary = {
        "positive": sum(1 for p in performances if p.ptype == "积极"),
        "negative": sum(1 for p in performances if p.ptype == "消极"),
        "total": len(performances),
        "recent": [
            {"ptype": p.ptype, "content": p.content, "date": str(p.created_at)[:10]}
            for p in sorted_perfs[:5]
        ],
    }

    # 请假
    leaves = db.query(Leave).filter(Leave.student_id == student_id).all()
    leave_summary = {
        "total": len(leaves),
        "recent": [
            {"reason": l.reason, "start": l.start_date, "end": l.end_date, "status": l.status}
            for l in sorted(leaves, key=lambda x: x.created_at, reverse=True)[:5]
        ],
    }

    # 作业（技能维度优秀率）：submissions.student_id 指向 students.id，直接用 student.id
    submissions = db.query(Submission).filter(Submission.student_id == student.id).all()
    sub_ids = [s.id for s in submissions]
    excellent_ids = {
        ew.submission_id
        for ew in db.query(ExcellentWork.submission_id)
        .filter(ExcellentWork.submission_id.in_(sub_ids))
        .all()
    }
    excellent_count = sum(1 for s in submissions if s.id in excellent_ids)
    skill = round(excellent_count / len(submissions) * 100, 1) if submissions else 0

    # 四维雷达（与桌面端画像同口径）
    radar = {
        "academic": clamp_score(round(avg, 1)) if scores else 50,
        "moral": clamp_score(round(50 + point_delta * 2, 1)) if performances else 50,
        "attendance": clamp_score(round(100 - leave_summary["total"] * 5, 1)),
        "skill": clamp_score(round(skill, 1)),
    }

    tags = [
        t.tag
        for t in db.query(StudentProfileTag)
        .filter(StudentProfileTag.student_id == student_id)
        .all()
    ]

    return {
        "student": _student_out(db, student),
        "radar": radar,
        "score_summary": score_summary,
        "point_summary": point_summary,
        "leave_summary": leave_summary,
        "performance_summary": performance_summary,
        "tags": tags,
    }
