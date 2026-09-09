"""删除操作的级联清理辅助函数。

问题背景：删除学生账号（User）或学生档案（Student）时，若只删单条记录，
会残留大量孤儿数据：
- 学生账号（users）与档案（students）通过「班级 + 姓名」关联，删一个不删另一个会不一致；
- 学生档案被 11 张业务表（scores/submissions/attendance/performances/...）通过 student_id 引用；
- 头像文件（uploads/avatars/*）不会被自动清理。

SQLite 默认不开启外键约束，因此这些孤儿数据不会立刻报错，但会引发后续
接口的数据不一致（甚至 500）。故删除学生时必须级联清理。
"""
import os

from sqlalchemy.orm import Session

from app.models import (
    Attendance,
    Communication,
    Leave,
    Performance,
    ReturnRecord,
    Score,
    StudentBoardHistory,
    StudentComment,
    StudentProfileTag,
    Submission,
    Talk,
)

# 所有以 student_id 引用 students.id 的业务模型（按删除顺序，无特殊依赖）
_STUDENT_DATA_MODELS = [
    Score,
    Leave,
    Communication,
    Submission,
    Attendance,
    Performance,
    Talk,
    ReturnRecord,
    StudentComment,
    StudentProfileTag,
    StudentBoardHistory,
]


def purge_student_data(db: Session, student_id: int) -> None:
    """级联删除某学生档案关联的全部业务数据（不 commit，由调用方统一提交）。"""
    for model in _STUDENT_DATA_MODELS:
        db.query(model).filter(model.student_id == student_id).delete(
            synchronize_session=False
        )


def delete_avatar_file(avatar_url: str | None) -> None:
    """删除头像文件（avatar 形如 /uploads/avatars/xxx.png）。

    基于项目根目录（backend/ 上一级）解析相对路径；文件不存在则静默跳过。
    """
    if not avatar_url or not avatar_url.startswith("/uploads/avatars/"):
        return
    # avatar 路径形如 /uploads/avatars/xxx.png，实际存储在 <backend>/uploads/avatars/xxx.png
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    full = os.path.join(base, "uploads", "avatars", os.path.basename(avatar_url))
    try:
        if os.path.exists(full):
            os.remove(full)
    except OSError:
        # 头像文件清理失败不影响主流程（删除操作本身仍应成功）
        pass
