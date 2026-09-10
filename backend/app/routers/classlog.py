import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_teacher, get_current_user
from app.models import (
    Activity,
    ClassPlan,
    Leave,
    Performance,
    ReturnRecord,
    Schedule,
    Score,
    Student,
    StudentComment,
    Talk,
    TeacherPlan,
    User,
    WorkLog,
)
from app.audit import (
    attach_student,
    serialize_list_with_students,
    audit,
    student_name,
    active_student_id_query,
    active_classroom_id_query,
)
from app.utils import to_dict, normalize_page, parse_date
from app.schemas import (
    PerformanceOut,
    ReturnRecordCreate,
    ReturnRecordOut,
    StudentCommentOut,
    TalkCreate,
    TalkOut,
    WorkLogCreate,
)
from app.permissions import (
    is_any_admin,
    get_teacher_class_ids,
    is_student_in_teacher_classes,
    is_teacher_class_owner,
    apply_student_class_filter,
    apply_teacher_student_filter,
    ensure_student_operable,
    ensure_class_operable,
)

router = APIRouter(prefix="/api", tags=["班级日志"])

dep = require_teacher


def _filter_student_query(db: Session, model, user: User):
    """教师只能查询自己班级学生的记录；管理员查询全部。均排除退学学生。"""
    q = db.query(model)
    # 排除退学学生
    q = q.filter(model.student_id.in_(active_student_id_query(db)))
    # 教师班级过滤（复用统一权限过滤逻辑）
    q, _ = apply_teacher_student_filter(db, user, q, model)
    return q


def _check_student_permission(db: Session, user: User, student_id: int):
    """教师只能操作自己班级学生的记录；退学/毕业学生不可操作（教师与管理员均受限）。"""
    # 退学/毕业限制
    ensure_student_operable(db, student_id)
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
        raise HTTPException(status_code=403, detail="无权操作该学生的记录")


def _check_class_permission(db: Session, user: User, class_id: int):
    """教师只能操作自己负责班级的数据。"""
    if not is_any_admin(user) and not is_teacher_class_owner(db, user.id, class_id):
        raise HTTPException(status_code=403, detail="无权操作该班级的数据")


def _serialize_activity(x) -> dict:
    """把 Activity 转为对外字典，filepath 统一输出为字符串列表（兼容旧单值字符串）。"""
    d = to_dict(x)
    d["filepath"] = _parse_filepath(d.get("filepath"))
    return d


def _parse_filepath(value) -> list[str]:
    """把存储的 filepath 解析为列表。兼容旧数据（普通字符串单图）与新的 JSON 数组。"""
    if not value:
        return []
    if isinstance(value, list):
        return [v for v in value if v]
    # 已是 JSON 数组字符串
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [v for v in parsed if isinstance(v, str) and v]
    except (json.JSONDecodeError, TypeError):
        pass
    # 旧数据：单个普通路径字符串
    return [value]


def _encode_filepath(value) -> str | None:
    """把前端传入的 filepath（字符串或列表）编码为存储格式（JSON 数组字符串）。"""
    if not value:
        return None
    paths = value if isinstance(value, list) else [value]
    paths = [p for p in paths if isinstance(p, str) and p]
    if not paths:
        return None
    return json.dumps(paths, ensure_ascii=False)


# ---------------- 工作日志 ----------------
@router.get("/work-logs")
def list_work_logs(page: int = 1, page_size: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page, page_size = normalize_page(page, page_size)
    q = db.query(WorkLog)
    # 教师只看自己的日志；管理员看全部
    if not is_any_admin(user):
        q = q.filter(WorkLog.teacher_id == user.id)
    total = q.count()
    rows = q.order_by(WorkLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [to_dict(x) for x in rows], "total": total}


@router.post("/work-logs")
def create_work_log(payload: WorkLogCreate, user=Depends(dep), db: Session = Depends(get_db)):
    x = WorkLog(
        teacher_id=user.id,
        date=parse_date(payload.date),
        content=payload.content,
    )
    db.add(x)
    audit(db, user, "create_work_log", target=f"新增工作日志")
    db.commit()
    db.refresh(x)
    return to_dict(x)


@router.put("/work-logs/{log_id}")
def update_work_log(log_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    x = db.get(WorkLog, log_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    if not is_any_admin(user) and x.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作他人的日志")
    if payload.get("date") is not None:
        x.date = parse_date(payload["date"])
    if payload.get("content") is not None:
        x.content = payload["content"]
    audit(db, user, "update_work_log", target=f"日志#{log_id}")
    db.commit()
    db.refresh(x)
    return to_dict(x)


@router.delete("/work-logs/{log_id}")
def delete_work_log(log_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    x = db.get(WorkLog, log_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    if not is_any_admin(user) and x.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作他人的日志")
    db.delete(x)
    audit(db, user, "delete_work_log", target=f"日志#{log_id}")
    db.commit()
    return {"ok": True}


# ---------------- 班级计划 / 教师计划 ----------------
def _plan_crud(model, prefix, router):
    @router.get(f"/{prefix}")
    def list_plans(page: int = 1, page_size: int = 20, plan_type: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        page, page_size = normalize_page(page, page_size)
        q = db.query(model)
        # 教师只看自己的计划；管理员看全部
        if not is_any_admin(user):
            q = q.filter(model.teacher_id == user.id)
        if plan_type:
            q = q.filter(model.plan_type == plan_type)
        total = q.count()
        rows = q.order_by(model.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
        return {"items": [to_dict(x) for x in rows], "total": total}

    @router.post(f"/{prefix}")
    def create_plan(payload: dict, user=Depends(dep), db: Session = Depends(get_db)):
        title = (payload.get("title") or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="标题不能为空")
        x = model(
            teacher_id=user.id,
            title=title,
            plan_type=payload.get("plan_type", "计划"),
            content=payload.get("content", ""),
        )
        db.add(x)
        audit(db, user, "create_plan", target=f"新增计划-{title}")
        db.commit()
        db.refresh(x)
        return to_dict(x)

    @router.put(f"/{prefix}/{{item_id}}")
    def update_plan(item_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        x = db.get(model, item_id)
        if not x:
            raise HTTPException(status_code=404, detail="记录不存在")
        if not is_any_admin(user) and x.teacher_id != user.id:
            raise HTTPException(status_code=403, detail="无权操作他人的计划")
        for f in ("title", "plan_type", "content"):
            if f in payload and payload[f] is not None:
                setattr(x, f, payload[f])
        audit(db, user, "update_plan", target=f"计划#{item_id}")
        db.commit()
        db.refresh(x)
        return to_dict(x)

    @router.delete(f"/{prefix}/{{item_id}}")
    def delete_plan(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        x = db.get(model, item_id)
        if not x:
            raise HTTPException(status_code=404, detail="记录不存在")
        if not is_any_admin(user) and x.teacher_id != user.id:
            raise HTTPException(status_code=403, detail="无权操作他人的计划")
        db.delete(x)
        audit(db, user, "delete_plan", target=f"计划#{item_id}")
        db.commit()
        return {"ok": True}


_plan_crud(ClassPlan, "class-plans", router)
_plan_crud(TeacherPlan, "teacher-plans", router)


# ---------------- 课程表 ----------------
@router.get("/schedules")
def list_schedules(class_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Schedule)
    # 排除毕业班级的课程表
    q = q.filter(Schedule.class_id.in_(active_classroom_id_query(db)))
    # 教师只能查看自己负责班级的课程表
    if not is_any_admin(user):
        class_ids = get_teacher_class_ids(db, user.id)
        if class_ids:
            q = q.filter(Schedule.class_id.in_(class_ids))
        else:
            return {"items": [], "total": 0}
    if class_id:
        # 教师只能查看自己负责班级的课程表
        if not is_any_admin(user):
            _check_class_permission(db, user, class_id)
        q = q.filter(Schedule.class_id == class_id)
    rows = q.order_by(Schedule.day_of_week, Schedule.period).all()
    return {"items": [to_dict(x) for x in rows], "total": len(rows)}


@router.post("/schedules")
def create_schedule(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not payload.get("class_id"):
        raise HTTPException(status_code=400, detail="请选择班级")
    # 毕业限制
    ensure_class_operable(db, payload["class_id"])
    # 教师只能为自己负责的班级排课
    _check_class_permission(db, user, payload["class_id"])
    day_of_week = payload.get("day_of_week", 1)
    period = payload.get("period", 1)
    if not isinstance(day_of_week, int) or not (1 <= day_of_week <= 7):
        raise HTTPException(status_code=400, detail="星期应为 1-7")
    if not isinstance(period, int) or not (1 <= period <= 12):
        raise HTTPException(status_code=400, detail="节次应为 1-12")
    x = Schedule(
        class_id=payload["class_id"],
        day_of_week=day_of_week,
        period=period,
        subject=payload.get("subject"),
        teacher_name=payload.get("teacher_name"),
    )
    db.add(x)
    audit(db, user, "create_schedule", target=f"新增课表")
    db.commit()
    db.refresh(x)
    return to_dict(x)


@router.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    x = db.get(Schedule, schedule_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    # 毕业限制
    ensure_class_operable(db, x.class_id)
    # 教师只能删除自己负责班级的课程
    _check_class_permission(db, user, x.class_id)
    db.delete(x)
    audit(db, user, "delete_schedule", target=f"课表#{schedule_id}")
    db.commit()
    return {"ok": True}


# ---------------- 班级活动 ----------------
@router.get("/activities")
def list_activities(page: int = 1, page_size: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page, page_size = normalize_page(page, page_size)
    q = db.query(Activity)
    # 排除毕业班级的活动
    q = q.filter(Activity.class_id.in_(active_classroom_id_query(db)))
    # 教师只能查看自己负责班级的活动
    if not is_any_admin(user):
        class_ids = get_teacher_class_ids(db, user.id)
        if class_ids:
            q = q.filter(Activity.class_id.in_(class_ids))
        else:
            return {"items": [], "total": 0}
    total = q.count()
    rows = q.order_by(Activity.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_serialize_activity(x) for x in rows], "total": total}


@router.post("/activities")
def create_activity(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="活动标题不能为空")
    # 毕业限制
    if payload.get("class_id"):
        ensure_class_operable(db, payload["class_id"])
    # 教师只能为自己负责的班级创建活动
    if payload.get("class_id"):
        _check_class_permission(db, user, payload["class_id"])
    x = Activity(
        class_id=payload.get("class_id"),
        title=title,
        content=payload.get("content", ""),
        filepath=_encode_filepath(payload.get("filepath")),
    )
    db.add(x)
    audit(db, user, "create_activity", target=f"新增活动")
    db.commit()
    db.refresh(x)
    return _serialize_activity(x)


@router.delete("/activities/{activity_id}")
def delete_activity(activity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    x = db.get(Activity, activity_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    # 毕业限制
    if x.class_id:
        ensure_class_operable(db, x.class_id)
    # 教师只能删除自己负责班级的活动
    if x.class_id:
        _check_class_permission(db, user, x.class_id)
    db.delete(x)
    audit(db, user, "delete_activity", target=f"活动#{activity_id}")
    db.commit()
    return {"ok": True}


# ---------------- 师生谈心 ----------------
@router.get("/talks")
def list_talks(page: int = 1, page_size: int = 20, student_id: int | None = None, class_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page, page_size = normalize_page(page, page_size)
    q = _filter_student_query(db, Talk, user)
    if class_id:
        q, denied = apply_student_class_filter(db, user, q, class_id, Talk)
        if denied:
            return {"items": [], "total": 0}
    if student_id:
        # 教师只能查看自己班级学生的谈心
        if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
            return {"items": [], "total": 0}
        q = q.filter(Talk.student_id == student_id)
    total = q.count()
    rows = q.order_by(Talk.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": serialize_list_with_students(db, rows), "total": total}


@router.post("/talks", response_model=TalkOut, status_code=201)
def create_talk(payload: TalkCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 教师只能与自己班级学生谈心
    _check_student_permission(db, user, payload.student_id)
    x = Talk(student_id=payload.student_id, teacher_id=user.id, content=payload.content)
    db.add(x)
    audit(db, user, "create_talk", target=f"新增谈心-{student_name(db, x.student_id)}", student_id=x.student_id, detail=f"内容：{(x.content or '')[:50]}")
    db.commit()
    db.refresh(x)
    return attach_student(db, to_dict(x), x.student_id)


@router.delete("/talks/{talk_id}")
def delete_talk(talk_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    x = db.get(Talk, talk_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    # 教师只能删除自己班级学生的谈心记录
    _check_student_permission(db, user, x.student_id)
    db.delete(x)
    audit(db, user, "delete_talk", target=f"谈心#{talk_id}-{student_name(db, x.student_id)}", student_id=x.student_id)
    db.commit()
    return {"ok": True}


# ---------------- 返校记录 ----------------
@router.get("/return-records")
def list_return_records(page: int = 1, page_size: int = 20, student_id: int | None = None, class_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page, page_size = normalize_page(page, page_size)
    q = _filter_student_query(db, ReturnRecord, user)
    if class_id:
        q, denied = apply_student_class_filter(db, user, q, class_id, ReturnRecord)
        if denied:
            return {"items": [], "total": 0}
    if student_id:
        # 教师只能查看自己班级学生的返校记录
        if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
            return {"items": [], "total": 0}
        q = q.filter(ReturnRecord.student_id == student_id)
    total = q.count()
    rows = q.order_by(ReturnRecord.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": serialize_list_with_students(db, rows), "total": total}


@router.post("/return-records", response_model=ReturnRecordOut, status_code=201)
def create_return_record(payload: ReturnRecordCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 教师只能为自己班级学生登记返校
    _check_student_permission(db, user, payload.student_id)
    x = ReturnRecord(
        student_id=payload.student_id,
        return_date=parse_date(payload.return_date),
        reason=payload.reason,
        note=payload.note,
    )
    db.add(x)
    audit(db, user, "create_return_record", target=f"新增返校-{student_name(db, x.student_id)}", student_id=x.student_id, detail=f"返校日期：{x.return_date or ''}；事由：{(x.reason or '')[:50]}")
    db.commit()
    db.refresh(x)
    return attach_student(db, to_dict(x), x.student_id)


@router.delete("/return-records/{record_id}")
def delete_return_record(record_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    x = db.get(ReturnRecord, record_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    # 教师只能删除自己班级学生的返校记录
    _check_student_permission(db, user, x.student_id)
    db.delete(x)
    audit(db, user, "delete_return_record", target=f"返校#{record_id}-{student_name(db, x.student_id)}", student_id=x.student_id)
    db.commit()
    return {"ok": True}


# ---------------- 学生表现 ----------------
@router.get("/performances")
def list_performances(page: int = 1, page_size: int = 20, student_id: int | None = None, class_id: int | None = None, ptype: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page, page_size = normalize_page(page, page_size)
    q = _filter_student_query(db, Performance, user)
    if class_id:
        q, denied = apply_student_class_filter(db, user, q, class_id, Performance)
        if denied:
            return {"items": [], "total": 0}
    if student_id:
        # 教师只能查看自己班级学生的表现
        if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
            return {"items": [], "total": 0}
        q = q.filter(Performance.student_id == student_id)
    if ptype:
        q = q.filter(Performance.ptype == ptype)
    total = q.count()
    rows = q.order_by(Performance.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": serialize_list_with_students(db, rows), "total": total}


@router.post("/performances", response_model=PerformanceOut, status_code=201)
def create_performance(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not payload.get("student_id"):
        raise HTTPException(status_code=400, detail="请选择学生")
    # 教师只能为自己班级学生登记表现
    _check_student_permission(db, user, payload["student_id"])
    ptype = payload.get("ptype", "积极")
    content = payload.get("content", "")
    # 分值：积极默认加分、消极默认减分，可手动指定
    points = payload.get("points")
    if points is None:
        points = 1 if ptype == "积极" else -1

    x = Performance(
        student_id=payload["student_id"],
        ptype=ptype,
        points=points,
        content=content,
        image=payload.get("image"),
    )
    db.add(x)
    audit(db, user, "create_performance", target=f"新增表现-{student_name(db, x.student_id)}", student_id=x.student_id, detail=f"类型：{x.ptype}；分值：{x.points}；内容：{(x.content or '')[:50]}")
    db.commit()
    db.refresh(x)
    return attach_student(db, to_dict(x), x.student_id)


@router.delete("/performances/{performance_id}")
def delete_performance(performance_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    x = db.get(Performance, performance_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    # 教师只能删除自己班级学生的表现
    _check_student_permission(db, user, x.student_id)
    db.delete(x)
    audit(db, user, "delete_performance", target=f"表现#{performance_id}-{student_name(db, x.student_id)}", student_id=x.student_id)
    db.commit()
    return {"ok": True}


# ---------------- 学生评语 ----------------
@router.get("/student-comments/suggest")
def suggest_student_comment(student_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """基于学生已有数据（成绩/表现/考勤/积分）生成评语草稿，供教师参考编辑。"""
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
        raise HTTPException(status_code=403, detail="无权为该学生生成评语")

    # 成绩
    scores = db.query(Score).filter(Score.student_id == student_id).all()
    score_avg = round(sum(s.score for s in scores) / len(scores), 1) if scores else None
    subjects = sorted({s.subject for s in scores})

    # 表现 + 积分
    performances = db.query(Performance).filter(Performance.student_id == student_id).all()
    positive = [p for p in performances if p.ptype == "积极"]
    negative = [p for p in performances if p.ptype == "消极"]
    point_delta = sum((p.points or 0) for p in performances)

    # 考勤
    leaves = db.query(Leave).filter(Leave.student_id == student_id).all()

    # 生成评语草稿（分段落，供教师删改）
    parts = []
    parts.append(f"{student.name}同学")

    # 学业段
    if scores:
        parts.append(
            f"本阶段共有 {len(scores)} 次成绩记录，平均分 {score_avg} 分"
            + (f"，涵盖科目：{'、'.join(subjects)}。" if subjects else "。")
        )
        if score_avg is not None:
            if score_avg >= 90:
                parts.append("学业表现优异，成绩名列前茅，望继续保持。")
            elif score_avg >= 75:
                parts.append("学业基础扎实，仍有提升空间，建议针对薄弱环节加强练习。")
            else:
                parts.append("学业上需加倍努力，建议制定学习计划，夯实基础。")

    # 表现段
    if positive or negative:
        seg = f"在校期间积极表现 {len(positive)} 次、消极表现 {len(negative)} 次"
        if positive:
            seg += f"，如「{positive[0].content}」等"
        parts.append(seg + "。")
        if len(positive) > len(negative):
            parts.append("整体表现积极向上，望继续发扬。")
        elif len(negative) > len(positive):
            parts.append("需注意行为规范，及时纠正不足，期待看到进步。")
        else:
            parts.append("表现总体平稳，望在自我管理上更进一步。")

    # 考勤段
    if leaves:
        parts.append(f"请假 {len(leaves)} 次，需关注作息与健康，保持良好出勤习惯。")
    elif not leaves and (scores or performances):
        parts.append("出勤情况良好，遵守校纪校规。")

    # 积分/总结段
    if point_delta != 0:
        parts.append(f"综合积分较基准 {'+' if point_delta > 0 else ''}{point_delta} 分，希望再接再厉。")

    content = "".join(parts)

    return {
        "student_id": student_id,
        "student_name": student.name,
        "content": content,
        "summary": {
            "score_avg": score_avg,
            "score_count": len(scores),
            "positive": len(positive),
            "negative": len(negative),
            "leave_count": len(leaves),
            "point_delta": point_delta,
        },
    }


@router.get("/student-comments")
def list_student_comments(page: int = 1, page_size: int = 20, student_id: int | None = None, class_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    page, page_size = normalize_page(page, page_size)
    q = _filter_student_query(db, StudentComment, user)
    if class_id:
        q, denied = apply_student_class_filter(db, user, q, class_id, StudentComment)
        if denied:
            return {"items": [], "total": 0}
    if student_id:
        # 教师只能查看自己班级学生的评语
        if not is_any_admin(user) and not is_student_in_teacher_classes(db, user.id, student_id):
            return {"items": [], "total": 0}
        q = q.filter(StudentComment.student_id == student_id)
    total = q.count()
    rows = q.order_by(StudentComment.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": serialize_list_with_students(db, rows), "total": total}


@router.post("/student-comments", response_model=StudentCommentOut, status_code=201)
def create_student_comment(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not payload.get("student_id"):
        raise HTTPException(status_code=400, detail="请选择学生")
    # 教师只能为自己班级学生写评语
    _check_student_permission(db, user, payload["student_id"])
    x = StudentComment(student_id=payload["student_id"], content=payload.get("content", ""))
    db.add(x)
    audit(db, user, "create_student_comment", target=f"新增评语-{student_name(db, x.student_id)}", student_id=x.student_id, detail=f"内容：{(x.content or '')[:80]}")
    db.commit()
    db.refresh(x)
    return attach_student(db, to_dict(x), x.student_id)


@router.put("/student-comments/{comment_id}", response_model=StudentCommentOut)
def update_student_comment(comment_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    x = db.get(StudentComment, comment_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    # 教师只能修改自己班级学生的评语
    _check_student_permission(db, user, x.student_id)
    if payload.get("content") is not None:
        x.content = payload["content"]
    audit(db, user, "update_student_comment", target=f"评语#{comment_id}-{student_name(db, x.student_id)}", student_id=x.student_id)
    db.commit()
    db.refresh(x)
    return attach_student(db, to_dict(x), x.student_id)


@router.delete("/student-comments/{comment_id}")
def delete_student_comment(comment_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    x = db.get(StudentComment, comment_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    # 教师只能删除自己班级学生的评语
    _check_student_permission(db, user, x.student_id)
    db.delete(x)
    audit(db, user, "delete_student_comment", target=f"评语#{comment_id}-{student_name(db, x.student_id)}", student_id=x.student_id)
    db.commit()
    return {"ok": True}
