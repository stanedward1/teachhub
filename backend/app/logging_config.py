"""结构化日志与请求追踪（request-id）。

提供跨请求全链路可追踪的最小可用实现：

- ``ContextVar`` 承载当前请求的 request-id，异步/线程上下文隔离。
- ``RequestIdFilter`` 把 request-id 注入每条日志记录的 ``record.request_id``。
- ``StructuredFormatter`` 输出单行结构化日志，便于日志采集系统解析。
- ``setup_logging`` 为 root 与控制台 handler 统一安装 formatter 与 filter。

不引入第三方依赖，全部基于标准库。
"""
import logging
import uuid
from contextvars import ContextVar, Token

# 当前请求的 request-id（无值时为空串，输出阶段回落为占位符 "-"）
_ctx_request_id: ContextVar[str] = ContextVar("request_id", default="")

# 无 request-id 时使用的占位符，保证日志格式恒为单行且字段完整
_REQUEST_ID_PLACEHOLDER = "-"

# 单行结构化日志格式：时间 级别 [rid=xxx] logger 名: 消息
LOG_FORMAT = "%(asctime)s %(levelname)s [rid=%(request_id)s] %(name)s: %(message)s"


def new_request_id() -> str:
    """生成一个新的 request-id（32 位十六进制）。"""
    return uuid.uuid4().hex


def get_request_id() -> str:
    """获取当前请求的 request-id；无值时返回占位符 ``-``。"""
    return _ctx_request_id.get() or _REQUEST_ID_PLACEHOLDER


def set_request_id(request_id: str) -> Token:
    """设置当前上下文的 request-id，返回用于 reset 的 token。"""
    return _ctx_request_id.set(request_id or "")


def reset_request_id(token: Token) -> None:
    """根据 token 还原 request-id 上下文（异常安全）。"""
    try:
        _ctx_request_id.reset(token)
    except (ValueError, LookupError):
        # token 已被还原或来自其他上下文，忽略即可
        pass


class RequestIdFilter(logging.Filter):
    """把当前 request-id 注入日志记录，缺失时填占位符 ``-``。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _ctx_request_id.get() or _REQUEST_ID_PLACEHOLDER
        return True


class StructuredFormatter(logging.Formatter):
    """单行结构化日志 formatter。"""

    def __init__(self, fmt: str = LOG_FORMAT, datefmt: str | None = None) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)


def setup_logging(level: int = logging.INFO) -> None:
    """为 root 与控制台 handler 安装结构化 formatter 与 request-id filter。

    幂等：重复调用不会重复添加控制台 handler；但会刷新 root 上所有 handler 的
    formatter/filter（run_migrations 的 alembic ``fileConfig`` 会重置 root handler）。
    """
    formatter = StructuredFormatter()
    request_id_filter = RequestIdFilter()

    root = logging.getLogger()
    # 迁移前可能为 NOTSET，迁移后可能被 alembic 抬到 WARNING，这里恢复到目标级别
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)

    # 确保存在带标记的控制台 handler（幂等）
    if not any(getattr(handler, "_teachhub_console", False) for handler in root.handlers):
        console = logging.StreamHandler()
        console.setLevel(logging.NOTSET)
        # 打标记，避免重复调用时重复添加
        setattr(console, "_teachhub_console", True)
        root.addHandler(console)

    # 统一为 root 上所有 handler 安装结构化 formatter 与 request-id filter
    for handler in root.handlers:
        handler.setFormatter(formatter)
        if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
            handler.addFilter(request_id_filter)
