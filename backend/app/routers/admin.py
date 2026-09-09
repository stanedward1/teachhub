from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.audit import audit
from app.cleanup import delete_avatar_file, purge_student_data
from app.database import get_db
from app.deps import get_current_user, require_school_admin, require_super_admin, require_teacher
from app.permissions import ensure_same_school, get_teacher_class_ids, is_any_admin, is_platform_admin
from app.models import (
    Assignment,
    Attendance,
    ClassTeacher,
    Classroom,
    Communication,
    Exam,
    Leave,
    OperationLog,
    Resource,
    School,
    Score,
    Setting,
    Student,
    Submission,
    User,
    WorkLog,
)
from app.security import hash_password
from app.utils import gen_student_no, to_dict, normalize_page

router = APIRouter(tags=["系统管理"])

# 账号管理 / 系统设置：仅学校管理员及以上（教师不可管理账号与全校设置）
admin_dep = require_school_admin


def _teachers_class_map(db: Session, teacher_ids):
    """批量查教师班主任班级名与科任班级名，避免 N+1。返回 (head_map, subject_map)。"""
    head_map: dict = {}
    subject_map: dict = {}
    if not teacher_ids:
        return head_map, subject_map
    head_rows = (
        db.query(Classroom.teacher_id, Classroom.name)
        .filter(Classroom.teacher_id.in_(teacher_ids))
        .all()
    )
    for tid, name in head_rows:
        head_map.setdefault(tid, []).append(name)
    ct_rows = (
        db.query(ClassTeacher.teacher_id, Classroom.name)
        .join(Classroom, Classroom.id == ClassTeacher.class_id)
        .filter(ClassTeacher.teacher_id.in_(teacher_ids))
        .all()
    )
    for tid, name in ct_rows:
        subject_map.setdefault(tid, []).append(name)
    return head_map, subject_map


def _users_out(db: Session, rows) -> list:
    """批量序列化用户：一次查班级名 + 一次查教师班级，避免 N+1。"""
    if not rows:
        return []
    class_ids = {u.class_id for u in rows if u.class_id}
    class_map = (
        {c.id: c.name for c in db.query(Classroom).filter(Classroom.id.in_(class_ids)).all()}
        if class_ids else {}
    )
    teacher_ids = [u.id for u in rows if u.role == "teacher"]
    head_map, subject_map = _teachers_class_map(db, teacher_ids)
    items = []
    for u in rows:
        d = to_dict(u)
        # 剥离敏感字段：密码哈希 + 安全状态，避免泄露
        d.pop("password_hash", None)
        d.pop("failed_attempts", None)
        d.pop("locked_until", None)
        d["class_name"] = class_map.get(u.class_id)
        if u.role == "teacher":
            d["head_classes"] = head_map.get(u.id, [])
            d["subject_classes"] = subject_map.get(u.id, [])
        items.append(d)
    return items


def _user_out(db: Session, u: User) -> dict:
    """单个用户序列化（含班主任/科任班级 + 剥离敏感字段）。"""
    return _users_out(db, [u])[0]


# ---------------- 账号管理 ----------------
@router.get("/api/admin/users")
def list_users(role: str = "", keyword: str = "", _=Depends(admin_dep), db: Session = Depends(get_db)):
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    if keyword:
        q = q.filter(User.name.contains(keyword) | User.username.contains(keyword))
    rows = q.order_by(User.id).all()
    return {"items": _users_out(db, rows), "total": len(rows)}


@router.post("/api/admin/users")
def create_user(payload: dict, user=Depends(admin_dep), db: Session = Depends(get_db)):
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or "123456"
    name = (payload.get("name") or "").strip()
    role = payload.get("role", "teacher")
    if not username or not name:
        raise HTTPException(status_code=400, detail="用户名和姓名不能为空")
    # 角色白名单：学校管理员可创建教师/学生；仅平台超管可创建学校管理员
    if role not in ("teacher", "school_admin", "student"):
        raise HTTPException(status_code=400, detail="角色不合法")
    if role == "school_admin" and not is_platform_admin(user):
        raise HTTPException(status_code=403, detail="只有平台超管可以创建学校管理员")
    # 多租户：用户名在学校内唯一（不同学校可存在同名教师）
    target_school_id = payload.get("school_id") or user.school_id
    if db.query(User).filter(
        User.school_id == target_school_id, User.username == username
    ).first():
        raise HTTPException(status_code=400, detail="该校已存在同名用户名")
    # 新用户默认密码 123456 不满足强度要求时，标记首次登录强制改密
    from app.security import validate_password_strength
    must_change = validate_password_strength(password) is not None
    u = User(
        username=username,
        password_hash=hash_password(password),
        name=name,
        role=role,
        phone=payload.get("phone"),
        class_id=payload.get("class_id") if role == "student" else None,
        school_id=payload.get("school_id") or user.school_id,
        must_change_password=must_change,
    )
    db.add(u)
    db.flush()
    # 学生账号必须同步建立学生档案，否则教师后台花名册查不到
    if role == "student" and u.class_id:
        cls = db.get(Classroom, u.class_id)
        if cls and not db.query(Student).filter(
            Student.class_id == u.class_id, Student.name == name
        ).first():
            db.add(
                Student(
                    school_id=cls.school_id,
                    class_id=u.class_id,
                    name=name,
                    student_no=gen_student_no(db, Student),
                    gender=payload.get("gender", "男"),
                    student_type="day",
                    status="active",
                )
            )
    audit(db, user, "create_user", target=f"{u.username} ({u.name})", detail=f"role={role}")
    db.commit()
    db.refresh(u)
    return _user_out(db, u)


@router.put("/api/admin/users/{user_id}")
def update_user(user_id: int, payload: dict, user=Depends(admin_dep), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    # 教师不能编辑其他教师/管理员的姓名、角色、班级归属（管理员不受限）
    if user.role == "teacher" and u.role in ("teacher", "school_admin", "super_admin"):
        if "name" in payload and payload["name"] is not None and payload["name"] != u.name:
            raise HTTPException(status_code=403, detail="教师无权修改其他教师或管理员的姓名")
        if "role" in payload and payload["role"] is not None:
            raise HTTPException(status_code=403, detail="教师无权修改其他教师或管理员的角色")
        if "class_id" in payload and payload["class_id"] is not None:
            raise HTTPException(status_code=403, detail="教师无权修改其他教师或管理员的班级信息")
    for f in ("name", "phone", "role", "class_id"):
        if f in payload and payload[f] is not None:
            setattr(u, f, payload[f])
    audit(db, user, "update_user", target=f"{u.username} ({u.name})", detail=f"fields={[f for f in ('name','phone','role','class_id') if f in payload and payload[f] is not None]}")
    db.commit()
    db.refresh(u)
    return _user_out(db, u)


@router.put("/api/admin/users/{user_id}/password")
def reset_password(user_id: int, payload: dict, user=Depends(admin_dep), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    # 教师不能重置其他教师/管理员的密码（只能重置学生密码；管理员可重置所有人）
    if user.role == "teacher" and u.role in ("teacher", "school_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="教师无权重置其他教师或管理员的密码")
    new_pwd = payload.get("password") or "123456"
    # 重置密码后标记首次登录需改密（除非新密码本身满足强度要求）
    from app.security import validate_password_strength
    u.must_change_password = validate_password_strength(new_pwd) is not None
    u.password_hash = hash_password(new_pwd)
    u.failed_attempts = 0
    u.locked_until = None
    audit(db, user, "reset_password", target=f"{u.username} ({u.name})")
    db.commit()
    return {"ok": True}


@router.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int, user=Depends(admin_dep), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    # 不能删除自己
    if u.id == user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    # 教师不能删除其他教师/管理员
    if user.role == "teacher" and u.role in ("teacher", "school_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="教师无权删除其他教师或管理员")
    # 平台超管可跨校删除；学校管理员仅能删除本校账号
    if not is_platform_admin(user):
        ensure_same_school(user, u.school_id)
    if is_platform_admin(u) and db.query(User).filter(User.role == "super_admin").count() <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个平台超管账号")

    # 删除学生账号时，级联清理对应的学生档案及其业务数据，避免孤儿数据导致后续接口异常
    if u.role == "student":
        stu = (
            db.query(Student)
            .filter(Student.class_id == u.class_id, Student.name == u.name)
            .first()
        )
        if stu:
            purge_student_data(db, stu.id)
            db.delete(stu)

    audit(db, user, "delete_user", target=f"{u.username} ({u.name})", detail=f"role={u.role}")
    db.delete(u)
    db.commit()

    # 删除头像文件（账号删除成功后清理磁盘文件，失败不影响结果）
    delete_avatar_file(u.avatar)
    return {"ok": True}


# ---------------- 系统设置 ----------------
@router.get("/api/settings")
def get_settings(_=Depends(admin_dep), db: Session = Depends(get_db)):
    rows = db.query(Setting).all()
    return {"items": [to_dict(s) for s in rows]}


@router.put("/api/settings/{key}")
def set_setting(key: str, payload: dict, user=Depends(admin_dep), db: Session = Depends(get_db)):
    # 校内唯一：按 (school_id, key) 定位，避免跨校同名配置冲突
    s = db.query(Setting).filter(
        Setting.school_id == user.school_id, Setting.key == key
    ).first()
    if not s:
        s = Setting(school_id=user.school_id, key=key, value=payload.get("value", ""))
        db.add(s)
    else:
        s.value = payload.get("value", s.value)
    db.commit()
    return {"ok": True}


@router.post("/api/settings/upgrade-grade")
def upgrade_grade(user=Depends(admin_dep), db: Session = Depends(get_db)):
    """年级升级：一年级→二年级……入学年份递增。"""
    classes = db.query(Classroom).all()
    order = {"一年级": 1, "二年级": 2, "三年级": 3, "四年级": 4, "五年级": 5, "六年级": 6}
    reverse = {v: k for k, v in order.items()}
    upgraded = 0
    for c in classes:
        cur = order.get(c.grade or "")
        if cur and cur < 6:
            c.grade = reverse[cur + 1]
            upgraded += 1
    audit(db, user, "upgrade_grade", detail=f"升级班级数={upgraded}")
    db.commit()
    return {"upgraded": upgraded}


# ---------------- 审计日志 ----------------
def _visible_audit_class_ids(db: Session, user: User):
    """返回可查看审计日志的班级范围。

    - admin：返回 None（查看全部）
    - 班主任：返回其班主任班级 id 列表
    - 科任老师（非任何班班主任）：返回空列表（无权查看）
    """
    if is_any_admin(user):
        return None
    return [c.id for c in db.query(Classroom).filter(Classroom.teacher_id == user.id).all()]


@router.get("/api/admin/audit-logs/actions")
def list_audit_log_actions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回所有出现过的操作类型（去重，供前端下拉框动态展示）。"""
    class_ids = _visible_audit_class_ids(db, user)
    if class_ids == []:
        raise HTTPException(status_code=403, detail="仅班主任或管理员可查看审计日志")
    rows = db.query(OperationLog.action).distinct().order_by(OperationLog.action).all()
    return {"items": [r[0] for r in rows]}


@router.get("/api/admin/audit-logs")
def list_audit_logs(
    action: str = "",
    keyword: str = "",
    date: str = "",
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page, page_size = normalize_page(page, page_size)
    """查询操作审计日志。管理员看全部；班主任看自己班级；科任老师不可见。"""
    class_ids = _visible_audit_class_ids(db, user)
    if class_ids == []:
        raise HTTPException(status_code=403, detail="仅班主任或管理员可查看审计日志")
    q = db.query(OperationLog)
    # 租户隔离：平台超管全局审计，其余角色仅本校
    if not is_platform_admin(user):
        q = q.filter(OperationLog.school_id == user.school_id)
    if class_ids is not None:
        q = q.filter(OperationLog.class_id.in_(class_ids))
    if action:
        q = q.filter(OperationLog.action == action)
    if keyword:
        q = q.filter(
            OperationLog.username.contains(keyword)
            | OperationLog.target.contains(keyword)
        )
    if date:
        # 查询该日 00:00:00 - 23:59:59 的日志
        from datetime import datetime, time
        try:
            d = datetime.strptime(date, "%Y-%m-%d").date()
            start = datetime.combine(d, time.min)
            end = datetime.combine(d, time.max)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")
        q = q.filter(OperationLog.created_at >= start, OperationLog.created_at <= end)
    total = q.count()
    rows = q.order_by(OperationLog.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [to_dict(x) for x in rows], "total": total}


# ---------------- 看板统计 ----------------
@router.get("/api/stats/dashboard")
def dashboard(user=Depends(require_teacher), db: Session = Depends(get_db)):
    # 教师只能查看自己负责班级的数据；管理员查看全校。
    # 均排除毕业班级与退学学生（看板不展示）。
    if not is_any_admin(user):
        teacher_class_ids = get_teacher_class_ids(db, user.id)
        class_ids = [c.id for c in db.query(Classroom).filter(
            Classroom.id.in_(teacher_class_ids), Classroom.is_graduated.is_(False)
        ).all()]
        student_ids = []
        if class_ids:
            student_ids = [s.id for s in db.query(Student).filter(
                Student.class_id.in_(class_ids), Student.is_dropped_out.is_(False)
            ).all()]
    else:
        cq = db.query(Classroom).filter(Classroom.is_graduated.is_(False))
        sq = db.query(Student).filter(Student.is_dropped_out.is_(False))
        # 学校管理员仅统计本校；平台超管 school_id 为空，统计全部
        if user.school_id is not None:
            cq = cq.filter(Classroom.school_id == user.school_id)
            sq = sq.filter(Student.school_id == user.school_id)
        class_ids = [c.id for c in cq.all()]
        student_ids = [s.id for s in sq.all()]

    def _count(model, id_col=None, ids=None):
        q = db.query(model)
        if id_col is not None and ids is not None:
            q = q.filter(id_col.in_(ids))
        return q.count()

    student_count = len(student_ids)
    class_count = len(class_ids)
    assignment_count = db.query(Assignment).count()
    submission_count = db.query(Submission).count()
    resource_count = db.query(Resource).count()
    exam_count = db.query(Exam).count()
    leave_count = _count(Leave, Leave.student_id, student_ids)
    comm_count = _count(Communication, Communication.student_id, student_ids)

    today = datetime.now().strftime("%Y-%m-%d")
    today_leaves = (
        db.query(Leave).filter(Leave.created_at >= today, Leave.student_id.in_(student_ids)).count()
        if student_ids is not None else db.query(Leave).filter(Leave.created_at >= today).count()
    )

    # 近 7 天请假详情（含人员姓名、类型、时长）：一次查询 + 批量加载，避免 N+1
    week_end = date.today()
    week_start = week_end - timedelta(days=6)
    week_leave_q = db.query(Leave).filter(Leave.start_date >= week_start, Leave.start_date <= week_end)
    if student_ids is not None:
        week_leave_q = week_leave_q.filter(Leave.student_id.in_(student_ids))
    week_leaves = week_leave_q.all()
    stu_ids = {l.student_id for l in week_leaves}
    stu_map = {s.id: s for s in db.query(Student).filter(Student.id.in_(stu_ids)).all()} if stu_ids else {}
    cls_ids = {s.class_id for s in stu_map.values() if s.class_id}
    cls_map = {c.id: c.name for c in db.query(Classroom).filter(Classroom.id.in_(cls_ids)).all()} if cls_ids else {}
    leaves_by_day: dict = {}
    for l in week_leaves:
        leaves_by_day.setdefault(l.start_date, []).append(l)
    trend = []
    leave_details = []
    for i in range(6, -1, -1):
        day = week_end - timedelta(days=i)
        day_leaves = leaves_by_day.get(day, [])
        items = []
        for l in day_leaves:
            stu = stu_map.get(l.student_id)
            class_name = cls_map.get(stu.class_id) if stu and stu.class_id else ""
            duration = 1
            if l.start_date and l.end_date:
                duration = (l.end_date - l.start_date).days + 1
            items.append({
                "name": stu.name if stu else "未知",
                "class_name": class_name,
                "reason": l.reason or "未填写",
                "duration": duration,
                "start": l.start_date or "",
                "end": l.end_date or "",
            })
        trend.append({"date": day.strftime("%m-%d"), "count": len(day_leaves)})
        leave_details.append({"date": day.strftime("%m-%d"), "count": len(day_leaves), "items": items})

    # 成绩分布（按考试名称分组，含百分比）
    score_q = db.query(Score)
    if student_ids is not None:
        score_q = score_q.filter(Score.student_id.in_(student_ids))
    score_rows = score_q.all()
    # 按考试名称分组：未命名考试归入 "日常测验"
    exam_groups = {}
    for s in score_rows:
        en = (s.exam_name or "").strip() or "日常测验"
        exam_groups.setdefault(en, []).append(s.score)
    score_dist_by_exam = {}
    for en, scs in sorted(exam_groups.items()):
        total_n = len(scs) if scs else 1
        score_dist_by_exam[en] = {
            "total": len(scs),
            "优秀(90+)": {"count": sum(1 for x in scs if x >= 90), "percent": round(sum(1 for x in scs if x >= 90) / total_n * 100, 1)},
            "良好(75-89)": {"count": sum(1 for x in scs if 75 <= x < 90), "percent": round(sum(1 for x in scs if 75 <= x < 90) / total_n * 100, 1)},
            "中等(60-74)": {"count": sum(1 for x in scs if 60 <= x < 75), "percent": round(sum(1 for x in scs if 60 <= x < 75) / total_n * 100, 1)},
            "待提高(<60)": {"count": sum(1 for x in scs if x < 60), "percent": round(sum(1 for x in scs if x < 60) / total_n * 100, 1)},
        }
    # 兼容旧前端：总体分布
    scores = [s.score for s in score_rows]
    total_scores = len(scores) if scores else 1
    dist = {
        "优秀(90+)": {"count": sum(1 for x in scores if x >= 90), "percent": round(sum(1 for x in scores if x >= 90) / total_scores * 100, 1)},
        "良好(75-89)": {"count": sum(1 for x in scores if 75 <= x < 90), "percent": round(sum(1 for x in scores if 75 <= x < 90) / total_scores * 100, 1)},
        "中等(60-74)": {"count": sum(1 for x in scores if 60 <= x < 75), "percent": round(sum(1 for x in scores if 60 <= x < 75) / total_scores * 100, 1)},
        "待提高(<60)": {"count": sum(1 for x in scores if x < 60), "percent": round(sum(1 for x in scores if x < 60) / total_scores * 100, 1)},
    }

    # 最近动态（请假 + 工作日志）
    recent = []
    leave_q = db.query(Leave)
    if student_ids is not None:
        leave_q = leave_q.filter(Leave.student_id.in_(student_ids))
    recent_leaves = leave_q.order_by(Leave.id.desc()).limit(5).all()
    rstu_ids = {l.student_id for l in recent_leaves}
    rstu_map = {s.id: s for s in db.query(Student).filter(Student.id.in_(rstu_ids)).all()} if rstu_ids else {}
    rcls_ids = {s.class_id for s in rstu_map.values() if s.class_id}
    rcls_map = {c.id: c.name for c in db.query(Classroom).filter(Classroom.id.in_(rcls_ids)).all()} if rcls_ids else {}
    for l in recent_leaves:
        stu = rstu_map.get(l.student_id)
        class_name = rcls_map.get(stu.class_id) if stu and stu.class_id else ""
        recent.append(
            {
                "type": "请假",
                "text": f"{class_name} {stu.name if stu else '未知'} 请假：{l.reason or '未填写'}",
                "time": l.created_at.strftime("%Y-%m-%d %H:%M") if l.created_at else "",
            }
        )
    # 最近动态的工作日志：教师只看自己的，管理员看全部
    wq = db.query(WorkLog)
    if user.role == "teacher":
        wq = wq.filter(WorkLog.teacher_id == user.id)
    for w in wq.order_by(WorkLog.id.desc()).limit(5).all():
        recent.append(
            {
                "type": "日志",
                "text": (w.content or "")[:30],
                "time": w.date or "",
            }
        )

    # 近 7 天出勤统计
    att_start = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    att_records = []
    if class_ids:
        att_records = db.query(Attendance).filter(
            Attendance.class_id.in_(class_ids),
            Attendance.date >= att_start,
            Attendance.date <= today,
        ).all()
    att_status = {"出勤": 0, "缺勤": 0, "请假": 0, "迟到": 0}
    att_trend_map = {}
    att_by_class_map = {}
    for r in att_records:
        if r.status in att_status:
            att_status[r.status] += 1
        day = att_trend_map.setdefault(r.date, {"出勤": 0, "缺勤": 0, "请假": 0, "迟到": 0})
        if r.status in day:
            day[r.status] += 1
        c = att_by_class_map.setdefault(r.class_id, {"出勤": 0, "缺勤": 0, "请假": 0, "迟到": 0})
        if r.status in c:
            c[r.status] += 1
    att_total = sum(att_status.values())
    # 遍历所有班级（含无考勤记录的班），确保管理员能看到每个班
    att_by_class = []
    for cid in class_ids:
        cls = db.get(Classroom, cid)
        st = att_by_class_map.get(cid, {"出勤": 0, "缺勤": 0, "请假": 0, "迟到": 0})
        total_n = sum(st.values())
        att_by_class.append(
            {
                "class_id": cid,
                "class_name": cls.name if cls else "",
                "rate": round(st["出勤"] / total_n * 100, 1) if total_n else 0,
                "total": total_n,
                "status": st,
            }
        )
    att_by_class.sort(key=lambda x: x["class_id"])
    attendance = {
        "rate": round(att_status["出勤"] / att_total * 100, 1) if att_total else 0,
        "status": att_status,
        "total": att_total,
        "trend": [
            {
                "date": d.strftime("%m-%d"),
                "rate": round(day["出勤"] / sum(day.values()) * 100, 1) if sum(day.values()) else 0,
            }
            for d, day in sorted(att_trend_map.items())
        ],
        "by_class": att_by_class,
    }

    # 当前教师身份（班主任/科任班级），用于看板专属标识
    if user.role == "teacher":
        head_classes = [c.name for c in db.query(Classroom).filter(Classroom.teacher_id == user.id).all()]
        subject_ids = [ct.class_id for ct in db.query(ClassTeacher).filter(ClassTeacher.teacher_id == user.id).all()]
        subject_classes = (
            [c.name for c in db.query(Classroom).filter(Classroom.id.in_(subject_ids)).all()]
            if subject_ids else []
        )
    else:
        head_classes = []
        subject_classes = []
    identity = {"head_classes": head_classes, "subject_classes": subject_classes}

    return {
        "identity": identity,
        "attendance": attendance,
        "counts": {
            "student": student_count,
            "class": class_count,
            "assignment": assignment_count,
            "submission": submission_count,
            "resource": resource_count,
            "exam": exam_count,
            "leave": leave_count,
            "communication": comm_count,
            "today_leave": today_leaves,
        },
        "leave_trend": trend,
        "leave_details": leave_details,
        "score_dist": dist,
        "score_dist_by_exam": score_dist_by_exam,
        "recent": recent,
    }


# ---------------- 平台超管：跨校概览 ----------------
@router.get("/api/admin/platform/overview")
def platform_overview(user=Depends(require_super_admin), db: Session = Depends(get_db)):
    """平台超管视角的全局统计：学校数、班级数、教师数、学生数及分校明细。"""
    schools = db.query(School).order_by(School.id).all()
    items = []
    for sc in schools:
        items.append({
            "id": sc.id,
            "name": sc.name,
            "code": sc.code,
            "status": sc.status,
            "class_count": db.query(Classroom).filter(Classroom.school_id == sc.id).count(),
            "student_count": db.query(Student).filter(Student.school_id == sc.id).count(),
            "teacher_count": db.query(User).filter(
                User.school_id == sc.id, User.role.in_(("teacher", "school_admin"))
            ).count(),
        })
    return {
        "school_count": len(schools),
        "active_school_count": sum(1 for x in schools if x.status == "active"),
        "student_count": sum(x["student_count"] for x in items),
        "teacher_count": sum(x["teacher_count"] for x in items),
        "items": items,
    }
