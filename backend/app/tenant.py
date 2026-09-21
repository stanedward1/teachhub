"""多租户上下文与 ORM 层自动隔离。

隔离全部由本模块的 ORM 事件统一完成：接口层只负责解析 JWT 写入租户上下文与角色鉴权，
不做查询过滤（技术方案原设计的「接口层显式过滤」辅助函数因从未接线，已于 2026-09-21 移除）。

- **租户上下文**：HTTP 中间件从 JWT 解析 `school_id` 写入 ContextVar，请求结束重置，
  避免线程池复用导致租户串号。
- **查询隔离**：`do_orm_execute` 事件为所有 SELECT 自动注入 `school_id = 当前租户`，
  包括 `db.get(Model, id)` —— 跨校记录直接返回 None（表现为 404，不泄露存在性）。
- **写入隔离**：`before_flush` 事件为新建对象自动填充 `school_id`。
- **平台超管**：`school_id` 为 NULL，不加过滤，可跨租户；未携带有效 JWT 的请求
  （登录、注册、公开接口）同样不过滤，由各接口的权限依赖负责鉴权。
"""
from contextlib import contextmanager
from contextvars import ContextVar, Token
from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

# (school_id, 是否激活过滤)
_tenant_school_id: ContextVar[int | None] = ContextVar("tenant_school_id", default=None)
_tenant_active: ContextVar[bool] = ContextVar("tenant_active", default=False)


def _tenant_models():
    """延迟获取含 school_id 列的映射类（模型导入完成后才可用）。"""
    from app.database import Base

    return tuple(
        m.class_ for m in Base.registry.mappers if hasattr(m.class_, "school_id")
    )


@lru_cache(maxsize=128)
def _criteria_options(school_id: int):
    """按租户缓存 loader criteria，避免每次查询重复构造。

    注意：这里必须传**表达式**而非 lambda —— SQLAlchemy 对 lambda criteria 做语句级缓存，
    闭包/默认参数会被当作常量，导致不同租户复用同一条编译结果（租户条件串号）。
    """
    return tuple(
        with_loader_criteria(model, model.school_id == school_id, include_aliases=True)
        for model in _tenant_models()
    )


def set_tenant(school_id: int | None) -> tuple[Token, Token]:
    """设置当前请求的租户上下文，返回用于 reset 的 token 对。"""
    t1 = _tenant_school_id.set(school_id)
    t2 = _tenant_active.set(True)
    return (t1, t2)


def reset_tenant(tokens: tuple[Token, Token]) -> None:
    """重置租户上下文（必须放在 finally 中执行）。"""
    t1, t2 = tokens
    _tenant_active.reset(t2)
    _tenant_school_id.reset(t1)


@contextmanager
def tenant_scope(school_id: int | None):
    """临时切换租户上下文（脚本/种子数据/跨租户任务使用）。

    school_id 传 None 表示平台超管视角：不加过滤、不注入 school_id。
    """
    tokens = set_tenant(school_id)
    try:
        yield
    finally:
        reset_tenant(tokens)


def assign_school_id(obj, school_id) -> None:
    """若对象含 school_id 且未赋值，则填入指定租户。"""
    if school_id is not None and hasattr(obj, "school_id"):
        if getattr(obj, "school_id", None) is None:
            obj.school_id = school_id


# ---------------- ORM 事件：自动隔离 ----------------
@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(state: ORMExecuteState):
    if not _tenant_active.get():
        return
    school_id = _tenant_school_id.get()
    if school_id is None:  # 平台超管：跨租户
        return
    if (
        not state.is_select
        or state.is_column_load
        or state.is_relationship_load
        or state.execution_options.get("skip_tenant_filter", False)
    ):
        return
    state.statement = state.statement.options(*_criteria_options(school_id))


@event.listens_for(Session, "before_flush")
def _fill_tenant_id(session: Session, flush_context, instances):
    if not _tenant_active.get():
        return
    school_id = _tenant_school_id.get()
    if school_id is None:
        return
    for obj in session.new:
        assign_school_id(obj, school_id)
