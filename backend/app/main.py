import logging
import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import run_migrations
from app.routers import admin, attendance, auth, classlog, homework, meta, mobile, students, uploads, workbench
from app.security import decode_token
from app.tenant import reset_tenant, set_tenant  # 导入即注册 ORM 租户隔离事件

# 基础日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """把 Pydantic 校验错误转为友好提示（否则前端只能拿到英文结构体）。"""
    errors = exc.errors()
    if errors:
        loc = [str(x) for x in errors[0].get("loc", []) if x not in ("body", "query", "path")]
        field = ".".join(loc) or "参数"
        return JSONResponse(status_code=422, content={"detail": f"参数校验失败：{field}"})
    return JSONResponse(status_code=422, content={"detail": "参数校验失败"})


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


@app.get("/")
def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
