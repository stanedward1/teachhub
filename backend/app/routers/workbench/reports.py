"""班级周报：周数据汇总 + 周报增删查。"""
import json

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.models import Classroom, Leave, Performance, Score, Student, WeeklyReport
from app.schemas import ReportSave
from app.config import BASE_POINTS
from app.routers.workbench._common import (
    dep,
    get_db,
    get_current_user,
    new_router,
    audit,
    active_classroom_id_query,
    ensure_class_operable,
    is_any_admin,
    is_teacher_class_owner,
    get_teacher_class_ids,
    to_dict,
    parse_date,
)

router = new_router("班级周报")


@router.get("/reports/weekly-data")
def get_weekly_data(class_id: int, week_start: str = "", week_end: str = "", user=Depends(get_current_user), db: Session = Depends(get_db)):
    if not is_any_admin(user):
        if not is_teacher_class_owner(db, user.id, class_id):
            raise HTTPException(status_code=403, detail="无权查看该班级周报")
    students = db.query(Student).filter(Student.class_id == class_id, Student.is_dropped_out.is_(False)).all()
    student_ids = [s.id for s in students]
    student_map = {s.id: s.name for s in students}
    total_students = len(students)
    if not student_ids:
        return {"error": "该班级无学生"}

    leave_q = db.query(Leave).filter(Leave.student_id.in_(student_ids))
    if week_start and week_end:
        leave_q = leave_q.filter(Leave.start_date >= week_start, Leave.start_date <= week_end)
    leaves = leave_q.all()

    perf_q = db.query(Performance).filter(Performance.student_id.in_(student_ids))
    if week_start and week_end:
        perf_q = perf_q.filter(Performance.created_at >= week_start, Performance.created_at <= week_end)
    performances = perf_q.all()
    positive_count = sum(1 for p in performances if p.ptype == "积极")
    negative_count = sum(1 for p in performances if p.ptype == "消极")

    score_q = db.query(Score).filter(Score.student_id.in_(student_ids))
    if week_start and week_end:
        score_q = score_q.filter(Score.created_at >= week_start, Score.created_at <= week_end)
    recent_scores = score_q.all()
    score_avg = round(sum(s.score for s in recent_scores) / len(recent_scores), 1) if recent_scores else 0

    all_leaves = db.query(Leave).filter(Leave.student_id.in_(student_ids)).all()
    all_perfs = db.query(Performance).filter(Performance.student_id.in_(student_ids)).all()

    point_map: dict = {}
    perf_map: dict = {}
    for p in all_perfs:
        point_map[p.student_id] = point_map.get(p.student_id, 0) + (p.points or 0)
        d = perf_map.setdefault(p.student_id, {"positive": 0, "negative": 0})
        if p.ptype == "积极":
            d["positive"] += 1
        else:
            d["negative"] += 1
    leave_map: dict = {}
    for l in all_leaves:
        leave_map[l.student_id] = leave_map.get(l.student_id, 0) + 1

    ranked = sorted(point_map.items(), key=lambda kv: kv[1], reverse=True)
    top5 = [{"name": student_map.get(sid, ""), "points": BASE_POINTS + total}
            for sid, total in ranked[:5] if student_map.get(sid)]
    bottom5 = [{"name": student_map.get(sid, ""), "points": BASE_POINTS + total}
               for sid, total in ranked[-5:] if student_map.get(sid)]

    profile_summaries = []
    for s in students[:10]:
        profile_summaries.append({
            "name": s.name,
            "student_no": s.student_no,
            "points": point_map.get(s.id, 0),
            "leave_count": leave_map.get(s.id, 0),
            "positive": perf_map.get(s.id, {}).get("positive", 0),
            "negative": perf_map.get(s.id, {}).get("negative", 0),
        })

    return {
        "class_id": class_id,
        "total_students": total_students,
        "leave_count": len(leaves),
        "attendance_rate": round((total_students * 5 - len(leaves)) / (total_students * 5) * 100, 1) if total_students else 0,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "score_avg": score_avg,
        "score_count": len(recent_scores),
        "top5": top5,
        "bottom5": bottom5,
        "profile_summaries": profile_summaries,
        "recent_performances": [
            {"student_name": student_map.get(p.student_id, ""), "ptype": p.ptype, "content": p.content}
            for p in sorted(performances, key=lambda x: x.created_at, reverse=True)[:15]
        ],
    }


@router.get("/reports")
def list_reports(class_id: int | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(WeeklyReport)
    q = q.filter(WeeklyReport.class_id.in_(active_classroom_id_query(db)))
    if not is_any_admin(user):
        class_ids = get_teacher_class_ids(db, user.id)
        if class_ids:
            q = q.filter(WeeklyReport.class_id.in_(class_ids))
        else:
            return {"items": [], "total": 0}
    if class_id:
        if not is_any_admin(user):
            if not is_teacher_class_owner(db, user.id, class_id):
                raise HTTPException(status_code=403, detail="无权查看该班级周报")
        q = q.filter(WeeklyReport.class_id == class_id)
    rows = q.order_by(WeeklyReport.id.desc()).all()
    items = []
    for r in rows:
        d = to_dict(r)
        cls = db.get(Classroom, r.class_id)
        d["class_name"] = cls.name if cls else ""
        if r.data_snapshot:
            try:
                d["snapshot"] = json.loads(r.data_snapshot)
            except (json.JSONDecodeError, TypeError):
                d["snapshot"] = {}
        items.append(d)
    return {"items": items, "total": len(rows)}


@router.post("/reports")
def save_report(payload: ReportSave, user=Depends(dep), db: Session = Depends(get_db)):
    report_id = payload.id
    title = payload.title.strip()
    class_id = payload.class_id
    if not is_any_admin(user) and class_id:
        if not is_teacher_class_owner(db, user.id, class_id):
            raise HTTPException(status_code=403, detail="无权为该班级生成周报")
    if report_id:
        r = db.get(WeeklyReport, report_id)
        if not r:
            raise HTTPException(status_code=404, detail="报告不存在")
        ensure_class_operable(db, r.class_id)
        if not is_any_admin(user):
            if not is_teacher_class_owner(db, user.id, r.class_id):
                raise HTTPException(status_code=403, detail="无权修改该周报")
        r.title = title
        r.content = payload.content
        r.data_snapshot = json.dumps(payload.data_snapshot, ensure_ascii=False)
    else:
        if class_id:
            ensure_class_operable(db, class_id)
        r = WeeklyReport(
            class_id=class_id,
            title=title,
            week_start=parse_date(payload.week_start),
            week_end=parse_date(payload.week_end),
            content=payload.content,
            data_snapshot=json.dumps(payload.data_snapshot, ensure_ascii=False),
            created_by=user.id,
        )
        db.add(r)
    audit(db, user, "save_report", target=f"保存周报")
    db.commit()
    db.refresh(r)
    return to_dict(r)


@router.delete("/reports/{report_id}")
def delete_report(report_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(WeeklyReport, report_id)
    if not r:
        raise HTTPException(status_code=404, detail="记录不存在")
    if not is_any_admin(user):
        if not is_teacher_class_owner(db, user.id, r.class_id):
            raise HTTPException(status_code=403, detail="无权删除该周报")
    db.delete(r)
    audit(db, user, "delete_report", target=f"周报#{report_id}")
    db.commit()
    return {"ok": True}
