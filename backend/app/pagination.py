"""分页工具：一次 SQL 同时取回「当前页数据 + 总数」，消除 ``count()`` 双查询。

原模式（两次数库往返）::

    total = q.count()
    rows = q.offset((page - 1) * page_size).limit(page_size).all()

新模式（一次往返）::

    from sqlalchemy import select
    from app.pagination import paginate

    stmt = select(Score).where(...).order_by(Score.id.desc())
    rows, total = paginate(db, stmt, page, page_size)

实现依赖窗口函数 ``COUNT(*) OVER ()``（MySQL 8 / SQLite 3.25+ / PostgreSQL 均支持），
在 LIMIT/OFFSET 之前对过滤后的结果集求总数，因此单次查询即可拿到 total。

仅当结果页为空（页码越界）时才回退一次 ``COUNT`` 查询，保证 ``total`` 语义与原
``q.count()`` 完全一致（避免"越界翻页显示总数为 0"的行为变化）。

注意：调用方传入的 ``stmt`` 必须是 **未加 offset/limit** 的 ``select()`` 语句
（可带 where / order_by / options），租户隔离由 ORM 事件自动叠加，无需手动处理。
"""
from sqlalchemy import func, select

__all__ = ["paginate"]


def paginate(db, stmt, page: int, page_size: int):
    """执行分页查询，返回 ``(rows, total)``。

    :param db: SQLAlchemy Session
    :param stmt: 已带过滤/排序的 ``select()``（不含 offset/limit）
    :param page: 页码，从 1 开始
    :param page_size: 每页条数
    """
    try:
        page = max(1, int(page or 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = max(1, int(page_size or 20))
    except (TypeError, ValueError):
        page_size = 20

    total_col = func.count().over().label("total_rows")
    paged = stmt.add_columns(total_col).offset((page - 1) * page_size).limit(page_size)

    result = db.execute(paged).all()
    if result:
        # 每一行形如 (实体, total_rows)，取实体的同时读回窗口函数算出的总数
        rows = [r[0] for r in result]
        return rows, int(result[0].total_rows or 0)

    # 空页（页码越界）：回退一次 COUNT，保持 total 语义与原实现一致
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    return [], int(total or 0)
