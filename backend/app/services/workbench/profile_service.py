"""学生数字画像业务逻辑：综合画像 + 标签管理。"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import StudentProfileTag
from app.permissions import ensure_student_visible
from app.schemas import StudentTagCreate
from app.services.student_stats import compute_student_stats
from app.services.students_service import _student_out
from app.services.workbench._common import (
    audit,
    ensure_student_operable,
    is_any_admin,
    is_student_in_teacher_classes,
    student_name,
    to_dict,
)


def get_student_profile(db: Session, user, student_id: int) -> dict:
    """获取学生综合数字画像数据。"""
    student = ensure_student_visible(
        db, user, student_id, detail_403="无权查看该学生画像", check_operable=False
    )

    # 共享统计核心：一次查询派生成绩/表现/积分/请假/优秀率/雷达原始统计，
    # 桌面端与移动端（mobile_service）共用同一公式；响应结构冻结。
    stats = compute_student_stats(db, student_id)

    score_summary = {
        "total": stats["score_count"],
        "avg": stats["score_avg"],
        "max": stats["score_max"],
        "min": stats["score_min"],
        "by_subject": {},
        "trend": [],
    }
    for row in stats["score_rows"]:  # asc（created_at 升序，与原 order_by 一致）
        score_summary["by_subject"].setdefault(row["subject"], []).append(
            {"score": row["score"], "exam": row["exam"], "date": row["date"]}
        )
        score_summary["trend"].append(
            {"subject": row["subject"], "score": row["score"], "exam": row["exam"], "date": row["date"]}
        )

    point_summary = {
        "total": stats["point_total"],
        "positive": stats["point_positive"],
        "negative": stats["point_negative"],
        "count": stats["point_count"],
        "timeline": stats["point_timeline"][:20],
    }
    performance_summary = {
        "positive": stats["perf_positive"],
        "negative": stats["perf_negative"],
        "total": stats["point_count"],
        "recent": stats["perf_recent"][:10],
    }

    leave_summary = {
        "total": stats["leave_total"],
        "recent": stats["leave_rows"][:10],
    }

    submission_summary = {
        "total": stats["submission_total"],
        "excellent": stats["excellent_count"],
        "rate": stats["excellent_rate"],
    }

    tags = db.query(StudentProfileTag).filter(StudentProfileTag.student_id == student_id).all()
    tag_list = [{"id": t.id, "tag": t.tag, "category": t.category} for t in tags]

    radar = stats["radar"]

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
    # 复用返回的 Student 以继承其 school_id（父资源租户归属）
    student = ensure_student_operable(db, student_id)
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
        raise HTTPException(status_code=403, detail="无权为该学生添加标签")
    tag = payload.tag.strip()
    t = StudentProfileTag(
        student_id=student_id,
        tag=tag,
        category=payload.category,
        # 显式继承学生档案的租户归属：超管上下文下 before_flush 不回填，
        # 落 NULL 会导致该标签对所有租户都不可见。
        school_id=student.school_id,
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
