import logging
import os
import time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine_kwargs = {"connect_args": connect_args}
if not DATABASE_URL.startswith("sqlite"):
    # 关系型数据库连接池：pool_pre_ping 避免拿到失效连接，pool_recycle 防连接超时
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 1800,
    })

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def _perf_counter() -> float:
    """当前单调时钟读数（独立封装便于测试注入，避免污染全局 time 模块）。"""
    return time.perf_counter()


# ---------------- 慢 SQL 可观测（仅挂主 engine，不影响其他 create_engine 实例） ----------------
# 事件配对说明：before/after_cursor_execute 收到同一个 context 对象，起止时间戳
# 挂在 context 上即天然按语句配对，无共享可变状态，天然并发安全。
@event.listens_for(engine, "before_cursor_execute")
def _slow_sql_before(conn, cursor, statement, parameters, context, executemany):
    """记录语句开始执行的时间戳。"""
    context._slow_sql_start = _perf_counter()


@event.listens_for(engine, "after_cursor_execute")
def _slow_sql_after(conn, cursor, statement, parameters, context, executemany):
    """语句执行完毕：耗时超过 SLOW_SQL_THRESHOLD_SECONDS 的记 WARNING。"""
    start = getattr(context, "_slow_sql_start", None)
    if start is None:
        return
    elapsed = _perf_counter() - start
    threshold = settings.SLOW_SQL_THRESHOLD_SECONDS
    if elapsed >= threshold:
        logger.warning(
            "[SLOW SQL] 耗时 %.2fs（阈值 %.2fs）: %s",
            elapsed,
            threshold,
            statement[:300],
        )


def run_migrations() -> None:
    """执行 Alembic 迁移到最新版本（schema 的唯一来源，失败即抛错）。

    注意：不再用 create_all 兜底建表。数据库 schema 由 Alembic 迁移链全权管理，
    迁移失败会直接抛异常让启动失败（fail-fast），避免版本号与实际表结构不一致。
    """
    from alembic import command
    from alembic.config import Config

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(backend_dir, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(cfg, "head")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

