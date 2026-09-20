import logging
import os
from logging.handlers import TimedRotatingFileHandler

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import run_migrations
from app.logging_config import (
    RequestIdFilter,
    StructuredFormatter,
    setup_logging,
)
from app.observability import render_metrics, request_logging_middleware
from app.routers import admin, attendance, auth, classlog, homework, meta, mobile, students, uploads, workbench
from app.security import decode_token
from app.tenant import reset_tenant, set_tenant  # 导入即注册 ORM 租户隔离事件

# 基础日志配置（结构化单行日志 + request-id）
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
setup_logging()


def _setup_file_logging() -> None:
    """把日志落盘到 backend/logs/teachhub.log（按天滚动，保留 30 天）。

    必须在 run_migrations() 之后调用：alembic 的 command.upgrade 会重置
    root logger 的 handler，若在此之前 addHandler 会被清空。

    同时显式把文件 handler 挂到 teachhub.access，并解除 uvicorn dictConfig
    （disable_existing_loggers=True）对该 logger 的禁用，确保访问日志落盘。
    """
    handler = TimedRotatingFileHandler(
        os.path.join(LOG_DIR, "teachhub.log"),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    handler.setFormatter(StructuredFormatter())
    handler.addFilter(RequestIdFilter())
    handler.setLevel(logging.INFO)

    root = logging.getLogger()
    if not any(isinstance(h, TimedRotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)

    # 访问日志 logger：强制启用并直接挂 handler，避免被 uvicorn 禁用
    access = logging.getLogger("teachhub.access")
    access.disabled = False
    access.propagate = False
    access.setLevel(logging.INFO)
    if not any(isinstance(h, TimedRotatingFileHandler) for h in access.handlers):
        access.addHandler(handler)

    # 迁移（alembic fileConfig）会重置 root handler/level，这里重新统一安装，
    # 确保控制台 handler 也带结构化 formatter + request-id filter。
    setup_logging()


logger = logging.getLogger("teachhub")

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description="""
## TeachHub —— 教学与班主任一体化工作平台

三大功能模块：

- **作业提交平台**（学生端）：学生登录后发布/提交作业、优秀作品互评、编程练习推荐
- **教师工作台**（管理端）：学生、成绩、考勤、积分、沟通、资源、试卷、座位
- **班级日志**（管理端）：工作日志、计划总结、课程表、活动、谈心、返校、表现、评语

### 权限说明

- `student` 学生 —— 仅能访问作业提交平台
- `teacher` 教师 / `school_admin` 学校管理员 —— 通过 `/admin` 进入后台，管理本校功能
- `super_admin` 平台超管 —— 跨学校管理全部租户

数据按 `school_id` 租户隔离，接口层与 ORM 层双重拦截。
""",
    version=settings.APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 限流：复用 auth 模块创建的 limiter 实例（slowapi 要求所有被 @limiter.limit 装饰的
# 路由共享同一个 Limiter 实例，否则计数会各自独立、限流失效）。
app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """把 Pydantic 校验错误转为友好提示（否则前端只能拿到英文结构体）。"""
    errors = exc.errors()
    if errors:
        loc = [str(x) for x in errors[0].get("loc", []) if x not in ("body", "query", "path")]
        field = ".".join(loc) or "参数"
        return JSONResponse(status_code=422, content={"detail": f"参数校验失败：{field}"})
    return JSONResponse(status_code=422, content={"detail": "参数校验失败"})


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request, exc: IntegrityError):
    """数据库完整性约束冲突 → 409，而不是笼统的 500。

    唯一性约束现在是**最后一道防线**：应用层会先做「先查后插」的友好校验（返回 400），
    但并发提交、批量导入、多条写入路径并存时仍可能撞上约束。这里统一收敛为 409 +
    中文提示，既避免把驱动的原始报错（含表名、字段名）泄漏给前端，也保证并发场景下
    用户看到的是可理解的提示而不是「服务器内部错误」。
    """
    raw = str(getattr(exc, "orig", exc))
    # ⚠️ 不同方言的报错文本形态不同，两边的特征串都要认，否则会静默落到通用分支：
    # - MySQL：`(1062, "Duplicate entry 'staff:1-x' for key 'users.uq_user_scope_username'")`
    #   报的是**索引名**，注意它含 `scope_username` 但**不含** `username_scope`；
    # - SQLite：`UNIQUE constraint failed: users.username_scope, users.username`
    #   报的是**列名**。
    if any(
        token in raw
        for token in ("uq_user_scope_username", "username_scope", "uq_user_class_username")
    ):
        detail = "该账号在本校（或本班）内已存在，请更换用户名"
    elif "foreign key" in raw.lower():
        detail = "数据冲突：关联的记录已不存在，请刷新后重试"
    else:
        detail = "数据冲突：已存在重复记录，请检查后重试"
    logger.warning("数据库完整性约束冲突: %s %s -> %s", request.method, request.url.path, raw)
    return JSONResponse(status_code=409, content={"detail": detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    """兜底异常处理：记录完整堆栈，返回统一的 500 结构，避免泄漏内部细节。"""
    logger.exception("未处理的异常: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请稍后重试"})


@app.middleware("http")
async def tenant_context_middleware(request, call_next):
    """从 JWT 解析 school_id 写入租户上下文，供 ORM 层自动隔离使用。

    - 无 Authorization：公开接口（登录/注册/学校列表），不加过滤
    - 平台超管：school_id 为 NULL，不加过滤（跨租户）
    - 其余账号：按 school_id 过滤
    - 旧版 token（payload 无 school_id 字段）：直接 401，强制重新登录
    """
    header = request.headers.get("authorization", "")
    tokens = None
    if header.lower().startswith("bearer "):
        try:
            payload = decode_token(header.split(" ", 1)[1].strip())
        except Exception:
            payload = None
        if payload is not None:
            if "school_id" not in payload:
                return JSONResponse(
                    status_code=401, content={"detail": "登录已过期，请重新登录"}
                )
            if payload.get("sub"):
                tokens = set_tenant(payload.get("school_id"))
    try:
        return await call_next(request)
    finally:
        if tokens is not None:
            reset_tenant(tokens)


# 访问日志 + 指标中间件（置于最外层，确保能记录到所有请求的最终状态与耗时）
app.middleware("http")(request_logging_middleware)


app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(auth.router)
app.include_router(meta.router)
app.include_router(homework.router)
app.include_router(students.router)
app.include_router(mobile.router)
app.include_router(attendance.router)
app.include_router(workbench.router)
app.include_router(classlog.router)
app.include_router(admin.router)
app.include_router(uploads.router)

# 数据库迁移：Alembic 是 schema 的唯一来源，启动时迁移到最新版本。
# 不再用 create_all 兜底建表，避免与 Alembic 交叉导致版本号/表结构不一致。
run_migrations()

# 迁移完成后配置日志落盘（alembic 会重置 root handler，须在其后设置）
_setup_file_logging()


@app.get("/")
def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    """Prometheus 指标端点：供 Prometheus / Grafana 抓取。"""
    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(render_metrics(), media_type="text/plain; version=0.0.4")
