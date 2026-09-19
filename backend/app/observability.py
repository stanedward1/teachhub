"""可观测性：请求访问日志 + 轻量 Prometheus 指标。

不引入第三方依赖，用标准库实现最小可用的可观测性：

- 访问日志中间件：记录每个请求的方法、路径、状态码、耗时（慢请求单独标注）。
- /metrics 端点：输出 Prometheus 文本格式，聚合请求计数、状态码分布、耗时直方图
  （分桶）、慢请求计数、进行中的请求数，供 Prometheus / Grafana 抓取。

计数基于进程内内存，适合单实例部署；多副本场景应改用 Redis/共享存储，
或接入 prometheus-fastapi + 独立 exporter。
"""
import logging
import time
from collections import defaultdict
from threading import Lock

from fastapi import Request

from app.logging_config import (
    new_request_id,
    reset_request_id,
    set_request_id,
)

# 请求头/响应头中的 request-id 字段名
_REQUEST_ID_HEADER = "X-Request-ID"

_access_logger = logging.getLogger("teachhub.access")

_mutex = Lock()

# 累计请求总数（按方法+路径）
_http_requests_total: dict = defaultdict(int)
# 状态码分布（按状态码）
_http_status_total: dict = defaultdict(int)
# 耗时直方图分桶（秒）
_HIST_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
_http_duration_buckets: dict = defaultdict(lambda: [0] * len(_HIST_BUCKETS))
# 慢请求（>= 1s）计数
_slow_requests_total: int = 0
# 进行中的请求数（瞬时）
_inflight_requests: int = 0


async def request_logging_middleware(request: Request, call_next):
    """访问日志中间件：绑定 request-id、记录请求耗时与状态，并累加指标。

    - 优先沿用上游传入的 ``X-Request-ID``（便于跨服务串联），否则生成新 id。
    - request-id 写入日志上下文，并在 finally 中还原，避免上下文泄漏。
    - 无论成功失败，都会把 request-id 回写到响应头 ``X-Request-ID``。
    """
    global _slow_requests_total, _inflight_requests

    request_id = request.headers.get(_REQUEST_ID_HEADER) or new_request_id()
    token = set_request_id(request_id)

    start = time.perf_counter()
    with _mutex:
        _inflight_requests += 1

    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed = time.perf_counter() - start
        status_code = response.status_code if response else 500
        with _mutex:
            _inflight_requests -= 1
            _http_requests_total[request.url.path] += 1
            _http_status_total[str(status_code)] += 1
            for i, bound in enumerate(_HIST_BUCKETS):
                if elapsed <= bound:
                    _http_duration_buckets[request.url.path][i] += 1
            if elapsed >= 1.0:
                _slow_requests_total += 1
        # 慢请求提升到 WARNING，便于日志采集系统快速定位
        if elapsed >= 1.0:
            _access_logger.warning(
                "%s %s %s %.1fms [SLOW]",
                request.method, request.url.path, status_code, elapsed * 1000,
            )
        else:
            _access_logger.info(
                "%s %s %s %.1fms",
                request.method, request.url.path, status_code, elapsed * 1000,
            )
        # 回写 request-id，便于前端/网关按同一 id 排查
        if response is not None:
            response.headers[_REQUEST_ID_HEADER] = request_id
        reset_request_id(token)


def _escape_label(s: str) -> str:
    """转义 Prometheus label 值中的特殊字符。"""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def render_metrics() -> str:
    """生成 Prometheus 文本格式的指标。"""
    lines = []
    lines.append("# HELP teachhub_http_requests_total 累计 HTTP 请求数（按路径）。")
    lines.append("# TYPE teachhub_http_requests_total counter")
    for path, cnt in _http_requests_total.items():
        lines.append(f'teachhub_http_requests_total{{path="{_escape_label(path)}"}} {cnt}')

    lines.append("# HELP teachhub_http_status_total HTTP 响应状态码分布。")
    lines.append("# TYPE teachhub_http_status_total counter")
    for code, cnt in _http_status_total.items():
        lines.append(f'teachhub_http_status_total{{code="{code}"}} {cnt}')

    lines.append("# HELP teachhub_http_duration_seconds_bucket 请求耗时直方图（秒，按路径分桶）。")
    lines.append("# TYPE teachhub_http_duration_seconds_bucket histogram")
    for path, buckets in _http_duration_buckets.items():
        cumulative = 0
        for i, bound in enumerate(_HIST_BUCKETS):
            cumulative += buckets[i]
            lines.append(
                f'teachhub_http_duration_seconds_bucket{{path="{_escape_label(path)}",le="{bound}"}} {cumulative}'
            )
        lines.append(
            f'teachhub_http_duration_seconds_bucket{{path="{_escape_label(path)}",le="+Inf"}} {cumulative}'
        )

    lines.append("# HELP teachhub_slow_requests_total 慢请求（>=1s）总数。")
    lines.append("# TYPE teachhub_slow_requests_total counter")
    lines.append(f"teachhub_slow_requests_total {_slow_requests_total}")

    lines.append("# HELP teachhub_inflight_requests 当前进行中的请求数。")
    lines.append("# TYPE teachhub_inflight_requests gauge")
    lines.append(f"teachhub_inflight_requests {_inflight_requests}")

    return "\n".join(lines) + "\n"
