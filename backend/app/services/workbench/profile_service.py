"""学生数字画像业务逻辑：综合画像 + 标签管理。"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import BASE_POINTS
from app.models import (
    ExcellentWork,
    Leave,
    Performance,
    Score,
    Student,
    StudentProfileTag,
    Submission,
)
from app.schemas import StudentTagCreate
from app.services.students_service import _student_out
from app.services.workbench._common import (
    audit,
    ensure_student_operable,
    is_any_admin,
    is_student_in_teacher_classes,
    student_name,
    to_dict,
)
from app.utils import clamp_score


def get_student_profile(db: Session, user, student_id: int) -> dict:
    """获取学生综合数字画像数据。"""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
        raise HTTPException(status_code=403, detail="无权查看该学生画像")

    scores = db.query(Score).filter(Score.student_id == student_id).order_by(Score.created_at).all()
    score_summary = {
        "total": len(scores),
        "avg": round(sum(s.score for s in scores) / len(scores), 1) if scores else 0,
        "max": max((s.score for s in scores), default=0),
        "min": min((s.score for s in scores), default=0),
        "by_subject": {},
        "trend": [],
    }
    for s in scores:
        score_summary["by_subject"].setdefault(s.subject, []).append({"score": s.score, "exam": s.exam_name or "", "date": str(s.created_at)[:10]})
        score_summary["trend"].append({"subject": s.subject, "score": s.score, "exam": s.exam_name or "", "date": str(s.created_at)[:10]})

    performances = db.query(Performance).filter(Performance.student_id == student_id).all()
    sorted_perfs = sorted(performances, key=lambda x: x.created_at, reverse=True)
    point_delta = sum((p.points or 0) for p in performances)
    point_summary = {
        "total": BASE_POINTS + point_delta,
        "positive": sum(v for v in ((p.points or 0) for p in performances) if v > 0),
        "negative": sum(v for v in ((p.points or 0) for p in performances) if v < 0),
        "count": len(performances),
        "timeline": [
            {"points": p.points or 0, "reason": p.content or "", "date": str(p.created_at)[:10]}
            for p in sorted_perfs[:20]
        ],
    }
    performance_summary = {
        "positive": sum(1 for p in performances if p.ptype == "积极"),
        "negative": sum(1 for p in performances if p.ptype == "消极"),
        "total": len(performances),
        "recent": [{"ptype": p.ptype, "content": p.content, "date": str(p.created_at)[:10]} for p in sorted_perfs[:10]],
    }

    leaves = db.query(Leave).filter(Leave.student_id == student_id).all()
    leave_summary = {
        "total": len(leaves),
        "recent": [{"reason": l.reason, "start": l.start_date, "end": l.end_date, "status": l.status} for l in leaves[:10]],
    }

    submissions = db.query(Submission).filter(Submission.student_id == student_id).all()
    excellent_ids = {
        ew.submission_id
        for ew in db.query(ExcellentWork.submission_id)
        .filter(ExcellentWork.submission_id.in_([s.id for s in submissions]))
        .all()
    }
    excellent_count = sum(1 for s in submissions if s.id in excellent_ids)
    submission_summary = {
        "total": len(submissions),
        "excellent": excellent_count,
        "rate": round(excellent_count / len(submissions) * 100, 1) if submissions else 0,
    }

    tags = db.query(StudentProfileTag).filter(StudentProfileTag.student_id == student_id).all()
    tag_list = [{"id": t.id, "tag": t.tag, "category": t.category} for t in tags]

    radar = {
        "academic": clamp_score(round(score_summary["avg"] if scores else 50, 1)),
        "moral": clamp_score(round(50 + point_delta * 2, 1)) if performances else 50,
        "attendance": clamp_score(round(100 - leave_summary["total"] * 5, 1)),
        "skill": clamp_score(round(submission_summary["rate"], 1)),
    }

    radar_basis = [
        {
            "key": "academic",
            "name": "学业",
            "score": radar["academic"],
            "source": "学生成绩记录（成绩管理模块）",
            "method": "按全部考试成绩取平均分，无成绩记录时默认 50 分，满分 100",
            "indicators": [
                f"考试记录 {score_summary['total']} 次",
                f"平均分 {score_summary['avg']} 分",
                f"最高 {score_summary['max']} 分 / 最低 {score_summary['min']} 分",
            ],
        },
        {
            "key": "moral",
            "name": "品德",
            "score": radar["moral"],
            "source": "学生表现记录（表现管理模块的分值字段，加分/扣分）",
            "method": "基准 50 分 + 表现分值净变化 × 2（上限 100），无记录时默认 50 分",
            "indicators": [
                f"积分总计 {point_summary['total']} 分",
                f"加分 {point_summary['positive']} 分 / 扣分 {point_summary['negative']} 分",
                f"积分记录 {point_summary['count']} 条",
            ],
        },
        {
            "key": "attendance",
            "name": "出勤",
            "score": radar["attendance"],
            "source": "请假/考勤记录（考勤管理模块）",
            "method": "满分 100 分，每请假 1 次扣 5 分，最低 0 分",
            "indicators": [
                f"请假记录 {leave_summary['total']} 次",
            ],
        },
        {
            "key": "skill",
            "name": "技能",
            "score": radar["skill"],
            "source": "作业提交与优秀作品（作业平台）",
            "method": "优秀率 = 优秀作品数 ÷ 提交总数 × 100，满分 100",
            "indicators": [
                f"提交 {submission_summary['total']} 次",
                f"优秀作品 {submission_summary['excellent']} 个",
                f"优秀率 {submission_summary['rate']}%",
            ],
        },
    ]

    return {
        "student": _student_out(db, student),
        "radar": radar,
        "radar_basis": radar_basis,
        "score_summary": score_summary,
        "point_summary": point_summary,
        "leave_summary": leave_summary,
        "performance_summary": performance_summary,
        "submission_summary": submission_summary,
        "tags": tag_list,
    }


def add_student_tag(db: Session, user, student_id: int, payload: StudentTagCreate) -> dict:
    """为学生新增画像标签。"""
    ensure_student_operable(db, student_id)
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
        raise HTTPException(status_code=403, detail="无权为该学生添加标签")
    tag = payload.tag.strip()
    t = StudentProfileTag(
        student_id=student_id,
        tag=tag,
        category=payload.category,
    )
    db.add(t)
    audit(db, user, "add_student_tag", target=f"标签-{student_name(db, student_id)}", student_id=student_id)
    db.commit()
    db.refresh(t)
    return to_dict(t)


def remove_student_tag(db: Session, user, student_id: int, tag_id: int) -> dict:
    """删除学生画像标签。"""
    ensure_student_operable(db, student_id)
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
        raise HTTPException(status_code=403, detail="无权删除该学生标签")
    t = db.get(StudentProfileTag, tag_id)
    if t and t.student_id == student_id:
        db.delete(t)
        audit(db, user, "remove_student_tag", target=f"标签#{tag_id}-{student_name(db, student_id)}", student_id=student_id)
        db.commit()
    return {"ok": True}
