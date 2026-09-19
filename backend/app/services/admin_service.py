"""系统管理业务逻辑（B1 分层：自 routers/admin.py 下沉，仅结构调整，行为完全不变）。

- 函数首参统一为 ``db: Session``，可抛 ``HTTPException`` 以保持与重构前一致的状态码与中文文案。
- 不 import 任何 router 模块。
"""
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.cleanup import delete_avatar_file, purge_student_data, purge_user_data
from app.permissions import (
    ensure_same_school,
    get_teacher_class_ids,
    is_any_admin,
    is_platform_admin,
)
from app.platform_settings import (
    ALLOW_REGISTRATION_KEY,
    is_registration_allowed,
    set_global_setting,
)
from app.schemas import RegistrationSetting
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
from app.security import hash_password, validate_password_strength
from app.utils import gen_student_no, to_dict, normalize_page
from app.pagination import paginate

# 成绩分布分段定义：(标签, 下界, 上界)，上界 None 表示无上界
_SCORE_BANDS = [
    ("优秀(90+)", 90, None),
    ("良好(75-89)", 75, 90),
    ("中等(60-74)", 60, 75),
    ("待提高(<60)", None, 60),
]

def _score_distribution(values) -> dict:
    """按固定分段统计成绩分布，返回 {标签: {count, percent}}。"""
    total = len(values) or 1
    dist = {}
    for label, lo, hi in _SCORE_BANDS:
        if lo is None:
            cnt = sum(1 for x in values if x < hi)
        elif hi is None:
            cnt = sum(1 for x in values if x >= lo)
        else:
            cnt = sum(1 for x in values if lo <= x < hi)
        dist[label] = {"count": cnt, "percent": round(cnt / total * 100, 1)}
    return dist


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


def _visible_audit_class_ids(db: Session, user: User):
    """返回可查看审计日志的班级范围。

    - admin：返回 None（查看全部）
    - 班主任：返回其班主任班级 id 列表
    - 科任老师（非任何班班主任）：返回空列表（无权查看）
    """
    if is_any_admin(user):
        return None
    return [c.id for c in db.query(Classroom).filter(Classroom.teacher_id == user.id).all()]


def _build_alerts(db: Session, user: User, class_ids: list, student_ids: list) -> dict:
    """聚合异常预警，返回可行动的洞察列表。

    - 连续缺勤：近 7 天缺勤次数 >= 3 的学生
    - 成绩骤降：最近一次考试较上一次下降 >= 20 分的学生
    - 待处理请假：状态为「登记」（未销假）的请假记录
    仅统计在籍学生，教师仅看自己负责班级、管理员看全校。
    """
    alerts = {"absenteeism": [], "score_drop": [], "pending_leave": []}
    if not student_ids:
        return alerts

    # 班级名映射（学生 -> 班级名）
    stu_rows = db.query(Student).filter(Student.id.in_(student_ids)).all()
    cls_map = {c.id: c.name for c in db.query(Classroom).filter(Classroom.id.in_(class_ids)).all()} if class_ids else {}
    stu_name = {s.id: s.name for s in stu_rows}
    stu_cls = {s.id: cls_map.get(s.class_id, "") for s in stu_rows}

    # 1) 连续缺勤：近 7 天缺勤 >= 3 次
    att_start = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    att_rows = (
        db.query(Attendance)
        .filter(
            Attendance.student_id.in_(student_ids),
            Attendance.status == "缺勤",
            Attendance.date >= att_start,
        )
        .all()
    )
    absent_count: dict = {}
    for r in att_rows:
        absent_count[r.student_id] = absent_count.get(r.student_id, 0) + 1
    for sid, cnt in absent_count.items():
        if cnt >= 3:
            alerts["absenteeism"].append({
                "student_id": sid,
                "name": stu_name.get(sid, "未知"),
                "class_name": stu_cls.get(sid, ""),
                "count": cnt,
            })
    alerts["absenteeism"].sort(key=lambda x: -x["count"])

    # 2) 成绩骤降：最近一次考试较上一次下降 >= 20 分
    score_rows = (
        db.query(Score)
        .filter(Score.student_id.in_(student_ids))
        .order_by(Score.student_id, Score.created_at)
        .all()
    )
    last_by_student: dict = {}
    for s in score_rows:
        key = s.student_id
        if key not in last_by_student:
            last_by_student[key] = []
        last_by_student[key].append(s)
    for sid, scs in last_by_student.items():
        if len(scs) < 2:
            continue
        prev, latest = scs[-2], scs[-1]
        drop = round(prev.score - latest.score, 1)
        if drop >= 20:
            alerts["score_drop"].append({
                "student_id": sid,
                "name": stu_name.get(sid, "未知"),
                "class_name": stu_cls.get(sid, ""),
                "subject": latest.subject,
                "prev": prev.score,
                "latest": latest.score,
                "drop": drop,
            })
    alerts["score_drop"].sort(key=lambda x: -x["drop"])

    # 3) 待处理请假（状态=登记，未销假）
    pending_leaves = (
        db.query(Leave)
        .filter(Leave.student_id.in_(student_ids), Leave.status == "登记")
        .order_by(Leave.created_at.desc())
        .limit(20)
        .all()
    )
    alerts["pending_leave"] = [
        {
            "leave_id": l.id,
            "name": stu_name.get(l.student_id, "未知"),
            "class_name": stu_cls.get(l.student_id, ""),
            "reason": l.reason or "未填写",
            "start": str(l.start_date) if l.start_date else "",
            "end": str(l.end_date) if l.end_date else "",
        }
        for l in pending_leaves
    ]

    return alerts


def list_users(db: Session, role: str = "", keyword: str = "") -> dict:
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    if keyword:
        q = q.filter(User.name.contains(keyword) | User.username.contains(keyword))
    rows = q.order_by(User.id).all()
    return {"items": _users_out(db, rows), "total": len(rows)}


def create_user(db: Session, payload: dict, user: User) -> dict:
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


def update_user(db: Session, user_id: int, payload: dict, user: User) -> dict:
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


def reset_password(db: Session, user_id: int, payload: dict, user: User) -> dict:
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    # 教师不能重置其他教师/管理员的密码（只能重置学生密码；管理员可重置所有人）
    if user.role == "teacher" and u.role in ("teacher", "school_admin", "super_admin"):
        raise HTTPException(status_code=403, detail="教师无权重置其他教师或管理员的密码")
    new_pwd = payload.get("password") or "123456"
    # 重置密码后标记首次登录需改密（除非新密码本身满足强度要求）
    u.must_change_password = validate_password_strength(new_pwd) is not None
    u.password_hash = hash_password(new_pwd)
    u.failed_attempts = 0
    u.locked_until = None
    audit(db, user, "reset_password", target=f"{u.username} ({u.name})")
    db.commit()
    return {"ok": True}


def delete_user(db: Session, user_id: int, user: User) -> dict:
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

    # 删除账号前，级联清理所有引用该 users.id 的业务数据，
    # 否则 MySQL 外键约束会拒绝删除（返回 500）
    purge_user_data(db, u.id)

    audit(db, user, "delete_user", target=f"{u.username} ({u.name})", detail=f"role={u.role}")
    db.delete(u)
    db.commit()

    # 删除头像文件（账号删除成功后清理磁盘文件，失败不影响结果）
    delete_avatar_file(u.avatar)
    return {"ok": True}


def get_settings(db: Session) -> dict:
    rows = db.query(Setting).all()
    return {"items": [to_dict(s) for s in rows]}


def set_setting(db: Session, key: str, payload: dict, user: User) -> dict:
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


def upgrade_grade(db: Session, user: User) -> dict:
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


def list_audit_log_actions(db: Session, user: User) -> dict:
    """返回所有出现过的操作类型（去重，供前端下拉框动态展示）。"""
    class_ids = _visible_audit_class_ids(db, user)
    if class_ids == []:
        raise HTTPException(status_code=403, detail="仅班主任或管理员可查看审计日志")
    rows = db.query(OperationLog.action).distinct().order_by(OperationLog.action).all()
    return {"items": [r[0] for r in rows]}


def audit_log_stats(db: Session, days: int = 30, user: "User | None" = None) -> dict:
    """审计日志统计（产品化：教师行为洞察）。

    返回：
    - by_teacher：按操作人聚合的操作次数（活跃度）
    - by_action：按操作类型聚合的次数（操作分布）
    - by_day：按日期聚合的次数（近 N 天趋势）
    - total：统计区间内日志总数
    权限与 list_audit_logs 一致：管理员看全校，班主任看自己班级。
    """
    days = max(1, min(days, 90))
    class_ids = _visible_audit_class_ids(db, user)
    if class_ids == []:
        raise HTTPException(status_code=403, detail="仅班主任或管理员可查看审计日志")

    since = datetime.now() - timedelta(days=days)
    q = db.query(OperationLog).filter(OperationLog.created_at >= since)
    if not is_platform_admin(user):
        q = q.filter(OperationLog.school_id == user.school_id)
    if class_ids is not None:
        q = q.filter(OperationLog.class_id.in_(class_ids))

    rows = q.all()
    total = len(rows)

    by_teacher: dict = {}
    by_action: dict = {}
    by_day: dict = {}
    for r in rows:
        uname = r.username or "未知"
        by_teacher[uname] = by_teacher.get(uname, 0) + 1
        by_action[r.action] = by_action.get(r.action, 0) + 1
        day = r.created_at.strftime("%Y-%m-%d") if r.created_at else ""
        if day:
            by_day[day] = by_day.get(day, 0) + 1

    # 教师活跃度：按次数倒序，Top 20
    teacher_list = sorted(
        [{"username": k, "count": v} for k, v in by_teacher.items()],
        key=lambda x: -x["count"],
    )[:20]
    # 操作分布：按次数倒序
    action_list = sorted(
        [{"action": k, "count": v} for k, v in by_action.items()],
        key=lambda x: -x["count"],
    )
    # 日趋势：按日期升序
    day_list = [{"date": k, "count": v} for k, v in sorted(by_day.items())]

    return {
        "total": total,
        "days": days,
        "by_teacher": teacher_list,
        "by_action": action_list,
        "by_day": day_list,
    }


def list_audit_logs(db: Session, action: str = "", keyword: str = "", date: str = "", page: int = 1, page_size: int = 20, user: "User | None" = None) -> dict:
    page, page_size = normalize_page(page, page_size)
    """查询操作审计日志。管理员看全部；班主任看自己班级；科任老师不可见。"""
    class_ids = _visible_audit_class_ids(db, user)
    if class_ids == []:
        raise HTTPException(status_code=403, detail="仅班主任或管理员可查看审计日志")
    stmt = select(OperationLog)
    # 租户隔离：平台超管全局审计，其余角色仅本校
    if not is_platform_admin(user):
        stmt = stmt.where(OperationLog.school_id == user.school_id)
    if class_ids is not None:
        stmt = stmt.where(OperationLog.class_id.in_(class_ids))
    if action:
        stmt = stmt.where(OperationLog.action == action)
    if keyword:
        stmt = stmt.where(
            OperationLog.username.contains(keyword)
            | OperationLog.target.contains(keyword)
        )
    if date:
        # 查询该日 00:00:00 - 23:59:59 的日志
        try:
            d = datetime.strptime(date, "%Y-%m-%d").date()
            start = datetime.combine(d, time.min)
            end = datetime.combine(d, time.max)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")
        stmt = stmt.where(OperationLog.created_at >= start, OperationLog.created_at <= end)
    # B2：单次 SQL 同时取回当前页与总数（COUNT(*) OVER ()），消除 count() 双查询
    stmt = stmt.order_by(OperationLog.id.desc())
    rows, total = paginate(db, stmt, page, page_size)
    return {"items": [to_dict(x) for x in rows], "total": total}


def dashboard(db: Session, user: User) -> dict:
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
    # 租户隔离（原实现为全表 count，学校管理员会看到全平台数量，属跨校串数）：
    # - 作业 / 资源 / 试卷按 school_id 过滤；平台超管 school_id 为空 → 统计全平台。
    # - 提交按校内学生过滤，与请假 / 沟通口径一致，同时排除毕业班级与退学学生。
    def _tenant_count(model):
        q = db.query(model)
        if user.school_id is not None:
            q = q.filter(model.school_id == user.school_id)
        return q.count()

    assignment_count = _tenant_count(Assignment)
    resource_count = _tenant_count(Resource)
    exam_count = _tenant_count(Exam)
    submission_count = _count(Submission, Submission.student_id, student_ids)
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
        d = _score_distribution(scs)
        d["total"] = len(scs)
        score_dist_by_exam[en] = d
    # 兼容旧前端：总体分布
    scores = [s.score for s in score_rows]
    dist = _score_distribution(scores)

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
    # 最近动态的工作日志：教师只看自己的；学校管理员只看本校教师的
    # （原实现为「管理员看全部」，会让学校管理员看到其它学校的工作日志）
    wq = db.query(WorkLog)
    if user.role == "teacher":
        wq = wq.filter(WorkLog.teacher_id == user.id)
    elif user.school_id is not None:
        wq = wq.filter(
            WorkLog.teacher_id.in_(
                db.query(User.id).filter(User.school_id == user.school_id)
            )
        )
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

    # 异常预警（可行动的洞察）：连续缺勤 / 成绩骤降 / 待处理请假
    alerts = _build_alerts(db, user, class_ids, student_ids)

    return {
        "identity": identity,
        "attendance": attendance,
        "alerts": alerts,
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


def platform_overview(db: Session, user: User) -> dict:
    """平台超管视角的全局统计：学校数、班级数、教师数、学生数及分校明细。"""
    schools = db.query(School).order_by(School.id).all()
    school_ids = [sc.id for sc in schools]
    # 一次聚合查询分校的班级数/学生数/教师数，避免逐校 count 的 N+1
    class_counts = (
        dict(db.query(Classroom.school_id, func.count()).filter(Classroom.school_id.in_(school_ids)).group_by(Classroom.school_id).all())
        if school_ids else {}
    )
    student_counts = (
        dict(db.query(Student.school_id, func.count()).filter(Student.school_id.in_(school_ids)).group_by(Student.school_id).all())
        if school_ids else {}
    )
    teacher_counts = (
        dict(
            db.query(User.school_id, func.count())
            .filter(User.school_id.in_(school_ids), User.role.in_(("teacher", "school_admin")))
            .group_by(User.school_id)
            .all()
        )
        if school_ids else {}
    )
    items = []
    for sc in schools:
        items.append({
            "id": sc.id,
            "name": sc.name,
            "code": sc.code,
            "status": sc.status,
            "class_count": class_counts.get(sc.id, 0),
            "student_count": student_counts.get(sc.id, 0),
            "teacher_count": teacher_counts.get(sc.id, 0),
        })
    return {
        "school_count": len(schools),
        "active_school_count": sum(1 for x in schools if x.status == "active"),
        "student_count": sum(x["student_count"] for x in items),
        "teacher_count": sum(x["teacher_count"] for x in items),
        "items": items,
    }


def platform_registration(db: Session, user: User) -> dict:
    """平台超管：查询「学生自助注册」总开关（全局作用域 school_id=None）。"""
    return {"allow_registration": is_registration_allowed(db)}


def set_platform_registration(db: Session, payload: RegistrationSetting, user: User) -> dict:
    """平台超管：开启/关闭「学生自助注册」总开关。

    全局作用域（school_id=None），跨校生效：关闭后后端注册接口拒绝注册，
    学生端登录页隐藏注册入口。写配置与审计日志在同一事务内提交。
    """
    value = "1" if payload.allow_registration else "0"
    set_global_setting(db, ALLOW_REGISTRATION_KEY, value)
    state_text = "开启" if payload.allow_registration else "关闭"
    audit(db, user, "toggle_registration", target=ALLOW_REGISTRATION_KEY, detail=f"{state_text}学生自助注册")
    db.commit()
    return {"allow_registration": payload.allow_registration}
