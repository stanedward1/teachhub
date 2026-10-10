"""学生画像共享统计核心（桌面端综合画像 + 移动端概览共用）。

只做**一次查询派生原始统计**（成绩 / 表现 / 积分 / 请假 / 作业优秀率 / 四维雷达），
返回纯 dict；**不做**权限校验、**不抛** HTTPException —— 404/403 与响应组装仍由
调用方（`profile_service.get_student_profile` / `mobile_service.mobile_student_overview`）负责。

🔴 两端响应结构冻结：字段名、recent 窗口长度、日期截断 `str(created_at)[:10]`、
排序方向全部由调用方保持，本模块只提供同一份底层数据，消除雷达公式在两文件
逐字重复的漂移风险。
"""
from sqlalchemy.orm import Session

from app.config import BASE_POINTS
from app.models import ExcellentWork, Leave, Performance, Score, Submission
from app.utils import clamp_score

# —— 四维雷达口径常量（桌面端 / 移动端共用同一公式） ——
RADAR_MORAL_WEIGHT = 2        # 品德维度：基准 50 分 + 积分净变化 × 2（上限 100）
RADAR_ATTENDANCE_PENALTY = 5  # 出勤维度：每请假 1 次扣 5 分（满分 100，最低 0）
RADAR_DEFAULT = 50            # 无记录时的默认分（品德无表现记录、学业无成绩记录）


def compute_student_stats(db: Session, student_id: int) -> dict:
    """一次查询派生学生画像的全部原始统计（纯数据，不含权限与组装逻辑）。"""
    # 成绩：按 created_at 升序（桌面端 by_subject/trend 依赖此顺序；移动端
    # recent 在此基础上稳定倒排，与原「无序查询 + sorted desc」等价）
    scores = (
        db.query(Score)
        .filter(Score.student_id == student_id)
        .order_by(Score.created_at)
        .all()
    )
    score_rows = [
        {"subject": s.subject, "score": s.score, "exam": s.exam_name or "", "date": str(s.created_at)[:10]}
        for s in scores
    ]
    score_rows_desc = [
        {"subject": s.subject, "score": s.score, "exam": s.exam_name or "", "date": str(s.created_at)[:10]}
        for s in sorted(scores, key=lambda x: x.created_at, reverse=True)
    ]

    # 表现 + 积分：一次查询派生两套口径
    performances = db.query(Performance).filter(Performance.student_id == student_id).all()
    sorted_perfs = sorted(performances, key=lambda x: x.created_at, reverse=True)
    point_delta = sum((p.points or 0) for p in performances)
    point_timeline = [
        {"points": p.points or 0, "reason": p.content or "", "date": str(p.created_at)[:10]}
        for p in sorted_perfs
    ]
    perf_recent = [
        {"ptype": p.ptype, "content": p.content, "date": str(p.created_at)[:10]}
        for p in sorted_perfs
    ]

    # 请假：桌面端 recent 取 DB 原序前 10，移动端按时间倒序前 5 —— 两个顺序都提供
    leaves = db.query(Leave).filter(Leave.student_id == student_id).all()
    leave_rows = [
        {"reason": l.reason, "start": l.start_date, "end": l.end_date, "status": l.status}
        for l in leaves
    ]
    leave_rows_desc = [
        {"reason": l.reason, "start": l.start_date, "end": l.end_date, "status": l.status}
        for l in sorted(leaves, key=lambda x: x.created_at, reverse=True)
    ]

    # 作业（技能维度优秀率）：submissions.student_id 指向 students.id
    submissions = db.query(Submission).filter(Submission.student_id == student_id).all()
    sub_ids = [s.id for s in submissions]
    excellent_ids = {
        ew.submission_id
        for ew in db.query(ExcellentWork.submission_id)
        .filter(ExcellentWork.submission_id.in_(sub_ids))
        .all()
    }
    excellent_count = sum(1 for s in submissions if s.id in excellent_ids)
    excellent_rate = round(excellent_count / len(submissions) * 100, 1) if submissions else 0

    radar = {
        "academic": clamp_score(round((sum(s.score for s in scores) / len(scores)), 1)) if scores else RADAR_DEFAULT,
        "moral": clamp_score(round(RADAR_DEFAULT + point_delta * RADAR_MORAL_WEIGHT, 1)) if performances else RADAR_DEFAULT,
        "attendance": clamp_score(round(100 - len(leaves) * RADAR_ATTENDANCE_PENALTY, 1)),
        "skill": clamp_score(round(excellent_rate, 1)),
    }

    return {
        "score_count": len(scores),
        "score_avg": round(sum(s.score for s in scores) / len(scores), 1) if scores else 0,
        "score_max": max((s.score for s in scores), default=0),
        "score_min": min((s.score for s in scores), default=0),
        "score_rows": score_rows,
        "score_rows_desc": score_rows_desc,
        "point_total": BASE_POINTS + point_delta,
        "point_positive": sum(v for v in ((p.points or 0) for p in performances) if v > 0),
        "point_negative": sum(v for v in ((p.points or 0) for p in performances) if v < 0),
        "point_count": len(performances),
        "point_timeline": point_timeline,
        "perf_positive": sum(1 for p in performances if p.ptype == "积极"),
        "perf_negative": sum(1 for p in performances if p.ptype == "消极"),
        "perf_recent": perf_recent,
        "leave_total": len(leaves),
        "leave_rows": leave_rows,
        "leave_rows_desc": leave_rows_desc,
        "submission_total": len(submissions),
        "excellent_count": excellent_count,
        "excellent_rate": excellent_rate,
        "radar": radar,
    }
