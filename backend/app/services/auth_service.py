"""认证域业务服务层（B1 分层 + F3 刷新令牌）。

承载登录 / 注册 / 改密 / 刷新 / 登出等业务逻辑与数据访问。router 层
（`app/routers/auth.py`）只做参数解析与调用，保持对外 API 契约（路径 / 字段 /
状态码 / 中文文案）与重构前**完全一致**，仅新增刷新令牌相关能力。

约定：
- 所有函数以 `db: Session` 作为第一个参数，保持无全局状态、可单测；
- 可抛 `HTTPException` 以逐字保持状态码与中文提示文案；
- 租户隔离由 `app/tenant.py` 的 ORM 事件自动完成；刷新令牌的按值检索显式声明
  `skip_tenant_filter`，避免刷新请求（通常无有效 access token）受上下文干扰。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import settings
from app.models import Classroom, RefreshToken, School, Student, User
from app.permissions import get_head_class_ids, get_student_account
from app.platform_settings import is_registration_allowed
from app.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    validate_password_strength,
    verify_password,
)
from app.utils import gen_student_no, to_dict

# 登录失败锁定策略（语义不变：连续失败 5 次锁定 15 分钟）
MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION_MINUTES = 15

# 等时代价用的哑哈希：账号不存在时也拿它跑一次 `verify_password`，让两条路径的
# 响应耗时对齐（见 `login` 的防盗枚举说明）。模块导入时生成一次，避免每请求重复计算；
# 用 `hash_password` 生成，保证 bcrypt cost 与真实口令哈希一致。
_DUMMY_PASSWORD_HASH = hash_password("teachhub-timing-equalizer-placeholder")


def _utcnow() -> datetime:
    """返回 naive UTC 当前时间，与无时区 `DateTime` 列保持一致，避免方言差异。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------- 登录安全辅助 ----------------
def _check_locked(user: User) -> None:
    """检查账号是否被锁定，若锁定则抛出 423 错误。"""
    if user.locked_until:
        now = datetime.now(timezone.utc)
        lock_until = user.locked_until
        if lock_until.tzinfo is None:
            lock_until = lock_until.replace(tzinfo=timezone.utc)
        if now < lock_until:
            remain = int((lock_until - now).total_seconds() // 60) + 1
            raise HTTPException(status_code=423, detail=f"账号已锁定，请 {remain} 分钟后再试")
        # 锁定已过期，重置
        user.locked_until = None
        user.failed_attempts = 0


def _record_failed_login(db: Session, user: User) -> None:
    """记录一次失败登录，达到阈值则锁定。"""
    user.failed_attempts = (user.failed_attempts or 0) + 1
    if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCK_DURATION_MINUTES)
        user.failed_attempts = 0
    db.commit()


def _reset_login_state(user: User) -> None:
    """登录成功后重置失败计数和锁定状态。"""
    if user.failed_attempts or user.locked_until:
        user.failed_attempts = 0
        user.locked_until = None


def _ensure_school_active(db: Session, user: User) -> None:
    """租户校验：停用学校的账号禁止登录（平台超管不属于任何学校，不受限）。"""
    if user.school_id is None:
        return
    school = db.get(School, user.school_id)
    if school and school.status != "active":
        raise HTTPException(status_code=403, detail="所属学校已停用，请联系平台管理员")


def _school_active_or_403(db: Session, school_id) -> None:
    """校验学校处于启用状态。"""
    if not school_id:
        return
    school = db.get(School, school_id)
    if school and school.status != "active":
        raise HTTPException(status_code=403, detail="该学校已停用，无法进行此操作")


def _resolve_login_user(db: Session, payload):
    """按学校维度定位账号，返回 (user, 失败提示文案)。

    - 学生：school_id + class_id + 姓名
    - 教师 / 学校管理员：school_id + 用户名
    - 平台超管：用户名（不属于任何学校）
    未传 school_id 时回退为全局唯一匹配，命中多个则要求前端选择学校。
    """
    if payload.class_id is not None:
        q = db.query(User).filter(
            User.role == "student",
            User.class_id == payload.class_id,
            User.name == payload.username,
        )
        if payload.school_id:
            q = q.filter(User.school_id == payload.school_id)
        users = q.all()
        err = "班级、姓名或密码错误"
    else:
        q = db.query(User).filter(User.username == payload.username, User.role != "student")
        if payload.school_id:
            q = q.filter(
                or_(User.school_id == payload.school_id, User.role == "super_admin")
            )
        users = q.all()
        err = "用户名或密码错误"
    if not users:
        return None, err
    if len(users) > 1:
        raise HTTPException(status_code=409, detail="该账号在多个学校中存在，请先选择学校")
    return users[0], err


def public_user(db: Session, user: User) -> dict:
    """把用户对象转为公开字典，剥离密码哈希与安全状态字段。

    额外补充两类**派生**信息，供前端做可见性判断（后端仍各自独立校验，前端判断只是
    「别把入口摆在那儿」，不构成安全边界）：
    - `class_name`：所属班级名；
    - `head_classes`：该教师担任**班主任**的班级 id 列表（非教师角色恒为 `[]`）。
      前端需要它才能判断「是否展示审计日志入口」—— 后端 `/admin/audit-logs` 刻意允许
      班主任查看本班日志（科任老师 403），而登录响应此前不含该信息，前端只能把教师
      一律拦下，导致该能力被前端屏蔽（见 docs/CHANGELOG.md 续 33）。
    """
    data = to_dict(user)
    # 剥离敏感字段：密码哈希 + 安全状态
    data.pop("password_hash", None)
    data.pop("failed_attempts", None)
    data.pop("locked_until", None)
    class_name = None
    if user.class_id:
        cls = db.get(Classroom, user.class_id)
        class_name = cls.name if cls else None
    data["class_name"] = class_name
    data["head_classes"] = get_head_class_ids(db, user.id) if user.role == "teacher" else []
    return data


# ---------------- 刷新令牌 ----------------
def _new_refresh_token(
    db: Session,
    user: User,
    user_agent: str | None = None,
) -> tuple[str, RefreshToken]:
    """构造一条刷新令牌记录（不提交），返回 (明文, 记录)。

    明文仅在签发时返回一次；落库的是 sha256 摘要。school_id 显式写入，不依赖
    `app/tenant.py` 的自动回填。
    """
    plain = create_refresh_token()
    row = RefreshToken(
        user_id=user.id,
        school_id=user.school_id,
        token_hash=hash_refresh_token(plain),
        expires_at=_utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        created_at=_utcnow(),
        user_agent=(user_agent or None),
    )
    db.add(row)
    return plain, row


def _load_refresh_token(db: Session, token_plain: str) -> RefreshToken | None:
    """按摘要检索刷新令牌；显式跳过租户过滤（刷新请求通常无有效 access token）。"""
    if not token_plain:
        return None
    return (
        db.query(RefreshToken)
        .execution_options(skip_tenant_filter=True)
        .filter(RefreshToken.token_hash == hash_refresh_token(token_plain))
        .first()
    )


def invalidate_user_sessions(db: Session, user: User) -> None:
    """让该账号的**全部既有会话**立即失效（不提交，由调用方 `commit`）。

    两件事缺一不可：

    1. `token_version += 1` —— access token 是无状态 JWT，无法逐个撤销；把版本号写进
       `tv` 声明、校验端比对（`app/deps.py`），即可让该用户此前签发的**全部** access
       token 立刻失效；
    2. **撤销该用户所有未撤销的 refresh token** —— 少了这步，攻击者仍可用旧 refresh
       换到一枚**带新版本号**的 access token，吊销就被完全绕过。

    调用场景：修改密码、管理员重置密码（即「改密 = 踢出所有设备」）。
    """
    user.token_version = (user.token_version or 0) + 1
    now = _utcnow()
    (
        db.query(RefreshToken)
        .execution_options(skip_tenant_filter=True)
        .filter(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .update({RefreshToken.revoked_at: now}, synchronize_session=False)
    )


# ---------------- 对外业务用例 ----------------
def _issue_session(db: Session, user: User, user_agent: str | None = None) -> dict:
    """签发一次完整会话（access + refresh）并提交，返回统一的响应负载。

    `login` 与 `register` **共用本函数**，避免两条「签发令牌」路径再次分叉：此前
    `register` 只签发 access token、不回传 `refresh_token`，导致注册后自动登录的学生
    在 access token（默认 24h）过期后**无法静默刷新**（也没有 refresh token 可供
    `/api/auth/logout` 注销），只能被踢回登录页重新输账号密码。

    Returns:
        形如 `{"token", "refresh_token", "user", "must_change_password"}` 的字典，
        字段名与登录接口契约一致（前端两条路径共用同一套消费逻辑）。
    """
    refresh_plain, _row = _new_refresh_token(db, user, user_agent=user_agent)
    db.commit()
    token = create_access_token(
        subject=str(user.id),
        role=user.role,
        school_id=user.school_id,
        token_version=user.token_version,
    )
    return {
        "token": token,
        "refresh_token": refresh_plain,
        "user": public_user(db, user),
        "must_change_password": bool(user.must_change_password),
    }


def login(
    db: Session,
    payload,
    user_agent: str | None = None,
) -> dict:
    """账号登录：校验凭证 / 锁定 / 租户 / 学籍，签发 access + refresh 令牌。

    响应在原有 `token` / `user` / `must_change_password` 基础上**新增** `refresh_token`。
    """
    user, err_msg = _resolve_login_user(db, payload)

    # 🔴 锁定检查必须早于密码校验。否则锁定期内的响应会被劈成两半：
    #   错口令 → 401（失败分支），对口令 → 423（才走到这里）。
    # 状态码差异即成为「口令是否正确」的 oracle —— 攻击者可无限次试探，
    # 5 次失败锁定形同虚设。
    # 注意：`_resolve_login_user` 可能返回 user=None（不存在 / 需先选学校），
    # 此时不判锁，保持既有「401 + 原 err_msg 文案」的响应不变。
    if user:
        _check_locked(user)

    # 🔴 恒定时序（防账号枚举）：账号不存在时也拿哑哈希跑一次 `verify_password`。
    # `bcrypt.checkpw` 是**故意慢**的，原先 `if not user or not verify_password(...)` 在
    # user 为 None 时短路跳过 bcrypt ⇒ 「账号存在」比「账号不存在」多一次 bcrypt 的耗时。
    # 攻击者不必看错误文案，只测响应时长即可枚举账号 —— 对学生登录（班级 + 姓名，
    # 姓名本身是低熵值）尤其有效。这里堵的是**时序**通道；状态码 oracle
    # （锁定期内 401 vs 423）是另一条通道，已在上面单独修复。
    password_ok = verify_password(
        payload.password, user.password_hash if user else _DUMMY_PASSWORD_HASH
    )
    if not user or not password_ok:
        if user:
            _record_failed_login(db, user)  # 错口令仍要记失败次数（语义不变）
        raise HTTPException(status_code=401, detail=err_msg)

    # 租户校验：停用学校拒绝登录
    _ensure_school_active(db, user)

    # 退学/毕业学生禁止登录
    if user.role == "student" and user.class_id:
        cls = db.get(Classroom, user.class_id)
        if cls and cls.is_graduated:
            raise HTTPException(status_code=403, detail="该班级已毕业，无法登录")
        stu = (
            db.query(Student)
            .filter(Student.class_id == user.class_id, Student.name == user.name)
            .first()
        )
        if stu and stu.is_dropped_out:
            raise HTTPException(status_code=403, detail="该学生已退学，无法登录")

    _reset_login_state(user)
    return _issue_session(db, user, user_agent=user_agent)


def _ensure_student_profile(db: Session, class_id: int, name: str) -> Student:
    """确保「班级 + 姓名」对应的学生档案存在（教师后台花名册的数据源）。"""
    stu = db.query(Student).filter(Student.class_id == class_id, Student.name == name).first()
    if stu:
        return stu
    cls = db.get(Classroom, class_id)
    stu = Student(
        school_id=cls.school_id if cls else None,
        class_id=class_id,
        name=name,
        student_no=gen_student_no(db, Student),
        gender="男",
        student_type="day",
        status="active",
    )
    db.add(stu)
    db.flush()
    return stu


def register(db: Session, payload, user_agent: str | None = None) -> dict:
    """学生自助注册（仅允许系统中尚不存在「班级+姓名」的学生）。

    注册即自动登录，因此与 `login` 一致地签发**完整会话**（access + refresh），
    见 `_issue_session`；响应额外带一个注册独有的 `user.student_id`。
    """
    # 平台总开关守卫：关闭时直接拒绝（早于任何参数校验）
    if not is_registration_allowed(db):
        raise HTTPException(status_code=403, detail="当前未开放注册，请联系管理员")
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="姓名不能为空")
    # 未选班级的学生不属于任何班级，教师无法管理，注册时必须选班级
    if not payload.class_id:
        raise HTTPException(status_code=400, detail="请选择班级")

    cls = db.get(Classroom, payload.class_id)
    if not cls:
        raise HTTPException(status_code=400, detail="所选班级不存在")
    # 已毕业班级不可再注册新学生
    if cls.is_graduated:
        raise HTTPException(status_code=403, detail="该班级已毕业，无法注册")
    _school_active_or_403(db, cls.school_id)

    # 校验是否已存在「班级 + 姓名」的学生账号
    exists = get_student_account(db, payload.class_id, name)
    if exists:
        raise HTTPException(status_code=409, detail="该学生已有账号，无需重复注册，请直接登录")

    # 同步创建学生档案，否则教师后台（花名册/考勤/作业/成绩）查不到该生
    student = _ensure_student_profile(db, payload.class_id, name)

    user = User(
        username=name,  # 用户名 = 姓名
        password_hash=hash_password(payload.password),
        name=name,
        role="student",
        school_id=cls.school_id,  # 租户归属，缺失会被教师查询的 school_id 过滤掉
        class_id=payload.class_id,
        # 自助注册同样遵守密码强度口径：弱口令不直接拒绝（保持既有注册体验），
        # 但强制其登录后修改，与教师建号路径（students_service 里
        # `must_change_password=validate_password_strength(pwd) is not None`）一致。
        must_change_password=validate_password_strength(payload.password) is not None,
    )
    db.add(user)
    db.flush()
    # 与 login 共用同一条签发路径（access + refresh + must_change_password）。
    # `student_id` 是注册独有的额外字段，补进 user 快照里。
    session = _issue_session(db, user, user_agent=user_agent)
    session["user"]["student_id"] = student.id
    return session


def change_password(db: Session, user: User, payload) -> dict:
    """修改当前用户密码（校验原密码与强度），成功清除强制改密标记并记审计。"""
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    # 密码强度校验
    err = validate_password_strength(payload.new_password)
    if err:
        raise HTTPException(status_code=400, detail=err)
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False  # 改密后清除强制改密标记
    # 🔴 改密即踢出该账号的**全部既有会话**（access + refresh）。前端在成功后本就
    # 会清理本地登录态并跳登录页，因此本人只需重新登录；而攻击者手里的旧令牌同时失效
    # —— 这才是「改密」应有的语义（原先只改哈希，旧令牌照常可用）。
    invalidate_user_sessions(db, user)
    audit(db, user, "change_password", target=user.username)
    db.commit()
    return {"ok": True}


def refresh(
    db: Session,
    refresh_token: str,
    user_agent: str | None = None,
) -> dict:
    """用刷新令牌换取新的令牌对（一次性轮换）。

    - 命中且未撤销、未过期 → 签发新 access token + 新 refresh token；
    - 旧行置 `revoked_at` 并将 `replaced_by` 指向新令牌摘要；
    - 否则一律 401 `{"detail": "登录已过期，请重新登录"}`。
    """
    row = _load_refresh_token(db, refresh_token)
    now = _utcnow()
    if (
        row is None
        or row.revoked_at is not None
        or row.expires_at is None
        or row.expires_at < now
    ):
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    user = (
        db.query(User)
        .execution_options(skip_tenant_filter=True)
        .filter(User.id == row.user_id)
        .first()
    )
    if user is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    # 轮换：签发新令牌并撤销旧令牌，新摘要写入旧行的 replaced_by
    new_plain, new_row = _new_refresh_token(db, user, user_agent=user_agent)
    row.revoked_at = now
    row.replaced_by = new_row.token_hash
    db.commit()

    token = create_access_token(
        subject=str(user.id),
        role=user.role,
        school_id=user.school_id,
        token_version=user.token_version,
    )
    return {"token": token, "refresh_token": new_plain, "token_type": "bearer"}


def logout(db: Session, refresh_token: str) -> dict:
    """登出：撤销匹配的刷新令牌；幂等（令牌不存在或已撤销也返回成功）。"""
    row = _load_refresh_token(db, refresh_token)
    if row is not None and row.revoked_at is None:
        row.revoked_at = _utcnow()
        db.commit()
    return {"ok": True}
