from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import School, User
from app.permissions import is_platform_admin
from app.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="无效的凭证")
    except Exception:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")

    # 租户上下文校验一：token 记录的学校与账号当前归属不一致（换校/迁校）需重新登录
    token_school_id = payload.get("school_id")
    if token_school_id is not None and token_school_id != user.school_id:
        raise HTTPException(status_code=401, detail="账号归属已变更，请重新登录")

    # 租户上下文校验二：停用学校的全部账号拒绝访问（平台超管不属于任何学校，不受限）
    if user.school_id is not None and not is_platform_admin(user):
        school = db.get(School, user.school_id)
        if school is None or school.status != "active":
            raise HTTPException(status_code=403, detail="所属学校已停用，请联系平台管理员")
    return user


def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="无权限访问该资源")
        return user

    return checker


# 学生：仅能访问作业提交平台相关接口
require_student = require_roles("student")
# 教师/管理员：可访问后台全部功能
require_teacher = require_roles("teacher", "school_admin", "super_admin")
# 学校管理员及以上
require_school_admin = require_roles("school_admin", "super_admin")
# 平台超管
require_super_admin = require_roles("super_admin")
