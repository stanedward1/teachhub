import re
import uuid
from datetime import datetime


def gen_student_no(db, student_model) -> str:
    """生成全局唯一学号（ZC + 日期 + 4 位随机），用于自助注册等无学号场景。"""
    for _ in range(50):
        no = "ZC" + datetime.now().strftime("%Y%m%d") + uuid.uuid4().hex[:4].upper()
        if not db.query(student_model).filter(student_model.student_no == no).first():
            return no
    raise RuntimeError("学号生成失败，请重试")


def to_dict(obj):
    """把 SQLAlchemy 模型实例转为字典（不含关系字段与内部状态）。"""
    if obj is None:
        return None
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def normalize_page(page, page_size, max_size: int = 200):
    """规范化分页参数：page >= 1，1 <= page_size <= max_size。"""
    try:
        page = int(page or 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(page_size or 20)
    except (TypeError, ValueError):
        page_size = 20
    return max(1, page), min(max(1, page_size), max_size)


def safe_filename(name: str) -> str:
    """过滤文件名中的非法字符，防止路径穿越。"""
    name = re.sub(r"[^\w.\-\u4e00-\u9fff]", "_", name or "")
    name = name.strip("._")
    return name or "file"
