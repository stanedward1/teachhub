"""学生基础数据路由（薄路由）：学校 / 班级 / 班级教师 / 学生 / 头像 / 寄宿历史 / 导出。

业务逻辑见 `app/services/students_service.py`。对外契约（路径 / 响应字段 / 状态码 / 中文
提示文案 / `audit` 文案）与重构前完全一致。
"""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_teacher
from app.models import User
from app.schemas import StudentCreate, StudentUpdate
from app.services import students_service

router = APIRouter(prefix="/api", tags=["基础数据"])


# ---------------- 学校 ----------------
@router.get("/schools")
def list_schools(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """学校列表：平台超管看全部，其他角色仅能看到自己所属学校。"""
    return students_service.list_schools(db, user)


@router.post("/schools")
def create_school(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return students_service.create_school(db, user, payload)


@router.put("/schools/{school_id}")
def update_school(school_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return students_service.update_school(db, user, school_id, payload)


@router.delete("/schools/{school_id}")
def delete_school(school_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return students_service.delete_school(db, user, school_id)


@router.put("/schools/{school_id}/status")
def set_school_status(
    school_id: int,
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """启用 / 停用学校（仅平台超管）。停用后该校全部账号不可登录。"""
    return students_service.set_school_status(db, user, school_id, payload)


# ---------------- 班级 ----------------
@router.get("/classrooms")
def list_classrooms(
    graduated: str = "",
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    return students_service.list_classrooms(db, user, graduated=graduated)


@router.post("/classrooms")
def create_classroom(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return students_service.create_classroom(db, user, payload)


@router.put("/classrooms/{class_id}")
def update_classroom(class_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return students_service.update_classroom(db, user, class_id, payload)


@router.delete("/classrooms/{class_id}")
def delete_classroom(class_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return students_service.delete_classroom(db, user, class_id)


# ---------------- 班级教师（班主任 + 科任） ----------------
@router.get("/classrooms/{class_id}/teachers")
def list_class_teachers(class_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """查看班级的教师（班主任 + 科任老师）。"""
    return students_service.list_class_teachers(db, user, class_id)


@router.post("/classrooms/{class_id}/teachers")
def add_class_teacher(class_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """添加科任老师（仅管理员）。"""
    return students_service.add_class_teacher(db, user, class_id, payload)


@router.delete("/classrooms/{class_id}/teachers/{teacher_id}")
def remove_class_teacher(class_id: int, teacher_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """移除科任老师（仅管理员）。"""
    return students_service.remove_class_teacher(db, user, class_id, teacher_id)


# ---------------- 学生 ----------------
@router.get("/students")
def list_students(
    class_id: int | None = None,
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    dropped_out: str = "",
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    return students_service.list_students(
        db, user, class_id=class_id, keyword=keyword, page=page, page_size=page_size, dropped_out=dropped_out
    )


@router.post("/students")
def create_student(payload: StudentCreate, user: User = Depends(require_teacher), db: Session = Depends(get_db)):
    return students_service.create_student(db, user, payload)


@router.put("/students/{student_id}")
def update_student(student_id: int, payload: StudentUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return students_service.update_student(db, user, student_id, payload)


@router.delete("/students/{student_id}")
def delete_student(student_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return students_service.delete_student(db, user, student_id)


@router.put("/students/{student_id}/password")
def reset_student_password(student_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """教师重置/修改学生密码（默认 123456）。"""
    return students_service.reset_student_password(db, student_id, payload, user)


@router.post("/students/{student_id}/avatar")
def upload_student_avatar(
    student_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """教师为学生上传头像。"""
    return students_service.upload_student_avatar(db, user, student_id, file)


@router.get("/students/board-type-stats")
def board_type_stats(class_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """通学生 / 寄宿生人数对比及明细名单（不含退学学生）。"""
    return students_service.board_type_stats(db, user, class_id=class_id)


@router.get("/students/{student_id}/board-history")
def get_board_history(student_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取学生寄宿/通学状态：当前状态、各时间段（含起始/结束时间）与变更日志。"""
    return students_service.get_board_history(db, user, student_id)


@router.get("/students/export")
def export_students(class_id: int | None = None, dropped_out: str = "", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return students_service.export_students(db, user, class_id=class_id, dropped_out=dropped_out)
