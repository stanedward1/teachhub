"""移动端专用轻量接口业务逻辑（B1 分层：自 routers/mobile.py 下沉，行为完全不变）。

面向班主任/管理员在手机端的「学生速查」场景：
- 列表精简字段、默认排除退学学生，降低移动端流量；
- 画像概览一次返回五维雷达 + 成绩/积分/表现等关键摘要，避免多次请求。
"""
from sqlalchemy.orm import Session

from app.models import Student, StudentProfileTag, User
from app.permissions import (
    ensure_student_visible,
    filter_students_by_teacher,
    is_any_admin,
)
from app.services.student_stats import compute_student_stats

# 学生序列化辅助统一取自 students service 层（B1 分层后 router 不再对外提供内部函数）。
from app.services.students_service import _student_out, _students_out


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


def mobile_students(
    db: Session, user: User, class_id: int | None = None, keyword: str = ""
) -> dict:
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


def mobile_student_overview(db: Session, user: User, student_id: int) -> dict:
    """移动端学生画像概览：五维雷达 + 成绩/积分/表现等关键摘要。"""
    student = ensure_student_visible(
        db, user, student_id, detail_403="无权查看该学生画像", check_operable=False
    )

    # 共享统计核心（与桌面端画像同源同公式）；响应结构冻结
    stats = compute_student_stats(db, student_id)

    score_summary = {
        "total": stats["score_count"],
        "avg": stats["score_avg"],
        "max": stats["score_max"],
        "min": stats["score_min"],
        "recent": stats["score_rows_desc"][:10],
    }

    # 表现 + 积分统计（一次查询派生两套口径；响应结构冻结）
    point_summary = {
        "total": stats["point_total"],
        "positive": stats["point_positive"],
        "negative": stats["point_negative"],
        "count": stats["point_count"],
        "recent": stats["point_timeline"][:10],
    }
    performance_summary = {
        "positive": stats["perf_positive"],
        "negative": stats["perf_negative"],
        "total": stats["point_count"],
        "recent": stats["perf_recent"][:5],
    }

    leave_summary = {
        "total": stats["leave_total"],
        "recent": stats["leave_rows_desc"][:5],
    }

    radar = stats["radar"]

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
