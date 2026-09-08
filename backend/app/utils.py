import re
import uuid
from datetime import date, datetime


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


def parse_date(value):
    """把前端传入的日期归一化为 `date` 对象，供 `Date` 列写入。

    - `None` / 空串 → `None`
    - `date` 对象 → 原样返回
    - `'YYYY-MM-DD'` 字符串 → `date`
    - 其他格式 → 抛 `ValueError`（由调用方转为 400）
    """
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        return datetime.strptime(value, "%Y-%m-%d").date()
    raise ValueError(f"无法解析的日期: {value!r}")


def clamp_score(value, lo: float = 0.0, hi: float = 100.0) -> float:
    """把数值钳制到 [lo, hi] 区间（用于雷达分数等 0-100 指标，避免出现负分）。"""
    return max(lo, min(hi, value))


def safe_filename(name: str) -> str:
    """过滤文件名中的非法字符，防止路径穿越。"""
    name = re.sub(r"[^\w.\-\u4e00-\u9fff]", "_", name or "")
    name = name.strip("._")
    return name or "file"
