import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import run_migrations
from app.routers import admin, attendance, auth, classlog, homework, meta, mobile, students, uploads, workbench

# 基础日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("techhub")

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description="""
## TechHub —— 教学与班主任一体化工作平台

三大功能模块：

- **作业提交平台**（学生端）：学生登录后发布/提交作业、优秀作品互评、编程练习推荐
- **教师工作台**（管理端）：学生、成绩、考勤、积分、沟通、资源、试卷、座位
- **班级日志**（管理端）：工作日志、计划总结、课程表、活动、谈心、返校、表现、评语

### 权限说明

- `student` 学生 —— 仅能访问作业提交平台
- `teacher` 教师 / `admin` 管理员 —— 通过 `/admin` 进入后台，管理全部功能
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
