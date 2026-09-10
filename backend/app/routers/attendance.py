"""学生考勤点名。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.audit import audit
from app.database import get_db
from app.deps import get_current_user
from app.models import Attendance, Student, User
from app.permissions import ensure_class_operable, is_any_admin, is_teacher_class_owner
from app.schemas import AttendanceCheckin
from app.utils import parse_date

router = APIRouter(prefix="/api", tags=["考勤"])

ATTENDANCE_STATUS = ("出勤", "缺勤", "请假", "迟到")


@router.get("/attendance")
def list_attendance(
    class_id: int = Query(..., gt=0, description="班级 ID"),
    date: str = Query(..., min_length=1, description="考勤日期（YYYY-MM-DD）"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询某班级某日的考勤：返回该班在籍学生及其状态（未点名默认出勤）。"""
    if not is_any_admin(user) and not is_teacher_class_owner(db, user.id, class_id):
        raise HTTPException(status_code=403, detail="无权查看该班级考勤")

    students = (
        db.query(Student)
        .filter(Student.class_id == class_id, Student.is_dropped_out.is_(False))
        .order_by(Student.id)
        .all()
    )
    records = (
        db.query(Attendance)
        .filter(Attendance.class_id == class_id, Attendance.date == date)
        .all()
    )
    record_map = {r.student_id: r.status for r in records}

    items = [
        {
            "student_id": s.id,
            "name": s.name,
            "student_no": s.student_no,
            "status": record_map.get(s.id, "出勤"),
        }
        for s in students
    ]
    return {"items": items, "total": len(items), "class_id": class_id, "date": date}


@router.post("/attendance/checkin", status_code=201)
def checkin(payload: AttendanceCheckin, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """批量提交点名结果（存在则更新，不存在则新增）。"""
    class_id = payload.class_id
    date = (payload.date or "").strip()
    records = payload.records
    if not class_id or not date or not records:
        raise HTTPException(status_code=400, detail="请提供班级、日期和点名记录")
    try:
        date = parse_date(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")

    # 毕业班级不可再点名
    ensure_class_operable(db, class_id)
    if not is_any_admin(user) and not is_teacher_class_owner(db, user.id, class_id):
        raise HTTPException(status_code=403, detail="无权为该班级点名")

    saved = 0
    for r in records:
        student_id = r.student_id
        status = r.status
        if status not in ATTENDANCE_STATUS:
            continue
        # 仅接受本班在籍学生
        student = db.get(Student, student_id)
        if not student or student.class_id != class_id or student.is_dropped_out:
            continue

        existing = (
            db.query(Attendance)
            .filter(
                Attendance.class_id == class_id,
                Attendance.student_id == student_id,
                Attendance.date == date,
            )
            .first()
        )
        if existing:
            existing.status = status
        else:
            db.add(Attendance(class_id=class_id, student_id=student_id, date=date, status=status))
        saved += 1

    audit(db, user, "attendance_checkin", target=f"班级#{class_id} {date} 考勤点名", class_id=class_id, detail=f"记录 {saved} 条")
    db.commit()
    return {"ok": True, "count": saved}


@router.get("/attendance/summary")
def attendance_summary(
    class_id: int = Query(..., gt=0, description="班级 ID"),
    start_date: str = Query(..., min_length=1, description="开始日期（YYYY-MM-DD）"),
    end_date: str = Query(..., min_length=1, description="结束日期（YYYY-MM-DD）"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """出勤率统计：某班级某日期范围内的出勤率、状态分布与逐日趋势。"""
    if not is_any_admin(user) and not is_teacher_class_owner(db, user.id, class_id):
        raise HTTPException(status_code=403, detail="无权查看该班级考勤统计")

    student_count = (
        db.query(Student)
        .filter(Student.class_id == class_id, Student.is_dropped_out.is_(False))
        .count()
    )

    records = (
        db.query(Attendance)
        .filter(
            Attendance.class_id == class_id,
            Attendance.date >= start_date,
            Attendance.date <= end_date,
        )
        .all()
    )

    status_count = {"出勤": 0, "缺勤": 0, "请假": 0, "迟到": 0}
    trend_map = {}
    for r in records:
        if r.status in status_count:
            status_count[r.status] += 1
        day = trend_map.setdefault(r.date, {"出勤": 0, "缺勤": 0, "请假": 0, "迟到": 0})
        if r.status in day:
            day[r.status] += 1

    total = sum(status_count.values())
    attendance_rate = round(status_count["出勤"] / total * 100, 1) if total else 0

    trend = []
    for d in sorted(trend_map.keys()):
        day = trend_map[d]
        day_total = sum(day.values())
        trend.append(
            {
                "date": d,
                "出勤": day["出勤"],
                "缺勤": day["缺勤"],
                "请假": day["请假"],
                "迟到": day["迟到"],
                "rate": round(day["出勤"] / day_total * 100, 1) if day_total else 0,
            }
        )

    return {
        "class_id": class_id,
        "start_date": start_date,
        "end_date": end_date,
        "student_count": student_count,
        "status_count": status_count,
        "total": total,
        "attendance_rate": attendance_rate,
        "trend": trend,
    }

