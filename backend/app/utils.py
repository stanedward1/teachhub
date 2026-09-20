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


def stringify_dates(d: dict) -> dict:
    """把 dict 中的 ``date`` / ``datetime`` 值转为 ISO 字符串（原地修改并返回）。

    供**带 `response_model` 的写接口**使用：响应模型中 `start_date` / `created_at` 等字段
    声明为 ``str``，而 Pydantic v2 不会把 date/datetime 强转为 str（否则触发
    ``ResponseValidationError``）。这里统一转为与 FastAPI ``jsonable_encoder`` 一致的
    ISO 形态，保证响应 JSON 与其它未声明 response_model 的列表接口形态一致。

    ⚠️ `to_dict()` 只做字段拷贝、**不做**日期转换，因此「`to_dict()` + 带 str 日期字段的
    `response_model`」必须在本函数里过一道，否则接口会在**写完库之后**才抛
    `ResponseValidationError` —— 客户端收到 500，数据却已经落库（重试即产生脏数据）。
    """
    if not isinstance(d, dict):
        return d
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, date):
            d[k] = v.isoformat()
    return d


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
