from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.audit import audit
from app.database import get_db
from app.deps import get_current_user
from app.models import Classroom, School, Student, User
from app.permissions import get_student_account
from app.schemas import LoginRequest, PasswordRequest, RegisterRequest
from app.security import (
    create_access_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.utils import gen_student_no, to_dict
import os
import uuid

router = APIRouter(prefix="/api/auth", tags=["认证"])

# 登录接口限流：按客户端 IP 维度限制登录尝试频率，配合应用层的账号锁定策略，
# 防止攻击者绕过账号锁定、用分布式 IP 对同一账号进行暴力破解。
# 注意：limiter 实例在 main.py 中创建并挂到 app.state，这里复用同一个实例
# （slowapi 要求所有路由共享同一个 Limiter 实例才能正确累计计数）。
limiter = Limiter(key_func=get_remote_address)

# 登录失败锁定策略
MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION_MINUTES = 15


def _check_locked(user: User):
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


def _record_failed_login(db: Session, user: User):
    """记录一次失败登录，达到阈值则锁定。"""
    user.failed_attempts = (user.failed_attempts or 0) + 1
    if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCK_DURATION_MINUTES)
        user.failed_attempts = 0
    db.commit()


def _reset_login_state(user: User):
    """登录成功后重置失败计数和锁定状态。"""
    if user.failed_attempts or user.locked_until:
        user.failed_attempts = 0
        user.locked_until = None


def _ensure_school_active(db: Session, user: User):
    """租户校验：停用学校的账号禁止登录（平台超管不属于任何学校，不受限）。"""
    if user.school_id is None:
        return
    school = db.get(School, user.school_id)
    if school and school.status != "active":
        raise HTTPException(status_code=403, detail="所属学校已停用，请联系平台管理员")


def _school_active_or_403(db: Session, school_id):
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
    from sqlalchemy import or_

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
    return data


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user, err_msg = _resolve_login_user(db, payload)
    if not user or not verify_password(payload.password, user.password_hash):
        if user:
            _record_failed_login(db, user)
        raise HTTPException(status_code=401, detail=err_msg)

    # 锁定检查（密码正确也要检查，防止锁定期间绕过）
    _check_locked(user)

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
    db.commit()

    token = create_access_token(subject=str(user.id), role=user.role, school_id=user.school_id)
    return {
        "token": token,
        "user": public_user(db, user),
        "must_change_password": bool(user.must_change_password),
    }


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


@router.post("/register")
@limiter.limit("10/minute")
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)):
    """学生自助注册（仅允许系统中尚不存在「班级+姓名」的学生）。"""
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
    )
    db.add(user)
    db.flush()
    data = public_user(db, user)
    data["student_id"] = student.id
    db.commit()
    token = create_access_token(subject=str(user.id), role=user.role, school_id=user.school_id)
    return {"token": token, "user": data}


@router.get("/schools")
def public_schools(db: Session = Depends(get_db)):
    """登录页学校下拉（无需登录）：仅返回启用中的学校。"""
    rows = db.query(School).filter(School.status == "active").order_by(School.id).all()
    return {"items": [{"id": s.id, "name": s.name, "code": s.code} for s in rows]}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"user": public_user(db, user)}


@router.put("/password")
def change_password(
    payload: PasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    # 密码强度校验
    err = validate_password_strength(payload.new_password)
    if err:
        raise HTTPException(status_code=400, detail=err)
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False  # 改密后清除强制改密标记
    audit(db, user, "change_password", target=user.username)
    db.commit()
    return {"ok": True}


_AVATAR_DIR = "uploads/avatars"
_AVATAR_MAX_SIZE = 2 * 1024 * 1024  # 2MB
_AVATAR_ALLOWED = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


@router.post("/avatar")
def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """学生 / 教师上传自己的头像。"""
    original = file.filename or "avatar"
    ext = os.path.splitext(original)[1].lower()
    if ext not in _AVATAR_ALLOWED:
        raise HTTPException(status_code=400, detail=f"仅支持图片格式：{'、'.join(sorted(_AVATAR_ALLOWED))}")

    name = f"avatar_{user.id}_{uuid.uuid4().hex[:8]}{ext}"
    os.makedirs(_AVATAR_DIR, exist_ok=True)
    dest = os.path.join(_AVATAR_DIR, name)

    size = 0
    chunk_size = 1024 * 1024
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = file.file.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > _AVATAR_MAX_SIZE:
                    f.close()
                    os.remove(dest)
                    raise HTTPException(status_code=413, detail=f"头像文件不能超过 {_AVATAR_MAX_SIZE // (1024*1024)}MB")
                f.write(chunk)
    except HTTPException:
        raise
    except Exception:
        if os.path.exists(dest):
            os.remove(dest)
        raise

    # 删除旧头像文件
    if user.avatar:
        old_name = user.avatar.rsplit("/", 1)[-1]
        old_full = os.path.join(_AVATAR_DIR, old_name)
        if os.path.exists(old_full):
            os.remove(old_full)

    user.avatar = f"/uploads/avatars/{name}"
    db.commit()
    return {"avatar": user.avatar}
