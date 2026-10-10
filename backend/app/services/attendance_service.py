"""学生考勤点名业务逻辑（B1 分层：自 routers/attendance.py 下沉，行为完全不变）。"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.audit import audit
from app.models import Attendance, Student, User
from app.permissions import ensure_class_operable, is_any_admin, is_teacher_class_owner
from app.schemas import AttendanceCheckin
from app.utils import parse_date_or_400

ATTENDANCE_STATUS = ("出勤", "缺勤", "请假", "迟到")


def list_attendance(db: Session, user: User, class_id: int, date: str) -> dict:
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


def checkin(db: Session, user: User, payload: AttendanceCheckin) -> dict:
    """批量提交点名结果（存在则更新，不存在则新增）。"""
    class_id = payload.class_id
    date = (payload.date or "").strip()
    records = payload.records
    if not class_id or not date or not records:
        raise HTTPException(status_code=400, detail="请提供班级、日期和点名记录")
    date = parse_date_or_400(date)

    # 毕业班级不可再点名（复用返回的 Classroom 以继承其 school_id）
    classroom = ensure_class_operable(db, class_id)
    if not is_any_admin(user) and not is_teacher_class_owner(db, user.id, class_id):
        raise HTTPException(status_code=403, detail="无权为该班级点名")

    # 先剔除状态非法的记录，再按 student_id 去重（保留首次出现）：
    # - 若先按 student_id 去重，同一学生「首条状态非法 + 次条合法」时会把整组丢掉
    #   （合法状态被一并丢弃）；先过滤可保证合法条目不因非法首条而丢失。
    # - database.py 配置 autoflush=False，循环内 `db.query(Attendance)...first()` 看不到本轮
    #   刚 `db.add` 的未 flush 行 ⇒ 同一 payload 里重复的 student_id 会被插两行，
    #   commit 时撞 uq_attendance_student_date → 409。去重后语义为「同生取首条状态」。
    records = [r for r in records if r.status in ATTENDANCE_STATUS]
    deduped: dict[int, object] = {}
    for r in records:
        deduped.setdefault(r.student_id, r)
    records = list(deduped.values())

    saved = 0
    for r in records:
        student_id = r.student_id
        status = r.status
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
            # 顺带修复历史脏行：school_id 落 NULL 的行在全租户下都不可见
            if existing.school_id is None:
                existing.school_id = classroom.school_id
        else:
            db.add(Attendance(
                class_id=class_id,
                student_id=student_id,
                date=date,
                status=status,
                # 显式继承父资源（班级）的租户归属，避免超管上下文下 school_id 落 NULL
                school_id=classroom.school_id,
            ))
        saved += 1

    audit(db, user, "attendance_checkin", target=f"班级#{class_id} {date} 考勤点名", class_id=class_id, detail=f"记录 {saved} 条")
    db.commit()
    return {"ok": True, "count": saved}


def attendance_summary(
    db: Session, user: User, class_id: int, start_date: str, end_date: str
) -> dict:
    """出勤率统计：某班级某日期范围内的出勤率、状态分布与逐日趋势。"""
    if not is_any_admin(user) and not is_teacher_class_owner(db, user.id, class_id):
        raise HTTPException(status_code=403, detail="无权查看该班级考勤统计")

    # 统计口径：本班在籍学生人数（非分页列表，保留 count())
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

    status_count = dict.fromkeys(ATTENDANCE_STATUS, 0)
    trend_map = {}
    for r in records:
        if r.status in status_count:
            status_count[r.status] += 1
        day = trend_map.setdefault(r.date, dict.fromkeys(ATTENDANCE_STATUS, 0))
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
