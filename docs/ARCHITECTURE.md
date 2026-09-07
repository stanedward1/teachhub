# TechHub 架构设计文档

> 版本：2.1 ｜ 更新：2026-09-07 ｜ 适用对象：后端 / 前端 / 测试 / 运维

## 1. 项目定位

TechHub 是一套面向中职学校的「教学 + 班主任一体化工作平台」，将原先分散的三个系统合并为**一套前后端分离**的应用：

| 原系统 | 定位 | 合并后形态 |
| ------ | ---- | ---------- |
| 在线作业提交平台 | 学生交作业、教师评优 | **学生端**（`/`） |
| 班级日志管理系统 | 班主任班级事务 | **管理端**模块（`/admin`） |
| 教师工作台 | 教师日常教务 | **管理端**模块（`/admin`） |

**核心设计目标**：一个账号、三角色、权限严格隔离。

## 2. 技术栈

| 层 | 技术 | 版本 | 说明 |
| --- | ---- | ---- | ---- |
| 后端框架 | FastAPI | 0.115 | 自动生成 OpenAPI 文档 |
| ORM | SQLAlchemy | 2.0 | 声明式模型 |
| 数据库 | SQLite | — | 单文件，可平滑切换 MySQL/PostgreSQL |
| 迁移 | Alembic | 1.13 | schema 唯一来源，`upgrade head` 建表/加列 |
| 认证 | python-jose + bcrypt | — | JWT（HS256）+ bcrypt 密码哈希 |
| 前端框架 | Vue 3 | 3.4 | Composition API + `<script setup>` |
| UI 库 | Element Plus | 2.7 | 后台与表单（桌面端） |
| 移动端 UI 库 | Vant | 4.10 | 移动端 H5（`/m`） |
| 图表 | ECharts | 5.5 | 数据看板、通宿生统计 |
| 构建 | Vite | 5.4 | 开发热更新 + 生产构建 |
| Markdown | marked + DOMPurify | 12 | 作业正文/日志渲染 + XSS 防护 |
| Excel | openpyxl | 3.1 | 导入/导出 |
| 测试 | pytest | — | 后端自动化测试 |
| 部署 | Docker + Nginx | — | 多阶段镜像 + 静态托管 + 反代 |

## 3. 目录结构

```
techhub/
├── backend/
│   ├── app/
│   │   ├── main.py            # 应用入口：CORS、静态挂载、路由注册、建表、迁移
│   │   ├── config.py          # 配置（env 驱动）
│   │   ├── database.py        # engine / SessionLocal / Base / get_db / run_migrations
│   │   ├── security.py        # 密码哈希 + JWT 签发/校验
│   │   ├── deps.py            # 依赖：get_current_user / require_roles
│   │   ├── utils.py           # to_dict / safe_filename 等工具
│   │   ├── audit.py           # 操作审计日志 + 批量查询辅助
│   │   ├── schemas.py         # Pydantic 请求/响应模型
│   │   ├── models/            # SQLAlchemy 模型（按域分组）
│   │   │   ├── user.py        #   User
│   │   │   ├── school.py      #   School / Classroom / ClassTeacher / Student
│   │   │   ├── homework.py    #   Assignment / AssignmentAttachment / Submission / ExcellentWork / WorkComment / SubmissionComment
│   │   │   ├── workbench.py   #   Score / Leave / Point / Communication / Resource / Exam / Seat / Setting / ImportHistory
│   │   │   ├── classlog.py    #   WorkLog / ClassPlan / TeacherPlan / Schedule / Activity / Talk / ReturnRecord / Performance / StudentComment
│   │   │   └── operation_log.py
│   │   ├── routers/           # 按业务域分组的 API 路由
│   │   │   ├── auth.py        #   登录/注册/密码
│   │   │   ├── meta.py        #   班级选项、编程练习（公开）
│   │   │   ├── homework.py    #   作业/提交/优秀作品/评论
│   │   │   ├── students.py    #   学校/班级/学生 CRUD + 班级教师（班主任+科任）+ 密码管理 + 通宿生统计
│   │   │   ├── workbench.py   #   教师工作台（成绩/请假/积分/沟通/资源/试卷/座位/画像/周报）+ 批量导入
│   │   │   ├── classlog.py    #   班级日志（日志/计划/课表/活动/谈心/返校/表现/评语）
│   │   │   ├── attendance.py  #   考勤点名 + 出勤率统计
│   │   │   ├── mobile.py      #   移动端专用接口（学生速查 + 画像概览）
│   │   │   ├── admin.py       #   账号管理 / 系统设置 / 数据看板 / 审计日志
│   │   │   └── uploads.py     #   通用文件上传
│   │   └── seed.py            # 假数据生成（Faker）
│   ├── tests/                 # pytest 自动化测试
│   ├── requirements.txt       # 运行时依赖
│   ├── requirements-dev.txt   # 开发/测试依赖
│   ├── run.py                 # uvicorn 启动入口
│   ├── Dockerfile             # 后端镜像
│   ├── docker-entrypoint.py   # 容器入口（迁移 + 首次 seed + 启动）
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/               # axios 封装 + 各域 API 函数
│   │   │   └── index.js       # 所有 API 接口定义
│   │   ├── router/            # 路由 + 角色守卫
│   │   ├── layout/            # StudentLayout / AdminLayout（可折叠侧边栏）
│   │   ├── components/        # Markdown / MarkdownEditor / StudentSelect
│   │   ├── mobile/            # 移动端（Vant）：layout + views + api
│   │   ├── views/student/     # 学生端页面（8 个）
│   │   └── views/admin/       # 管理端页面（22 个）
│   ├── vite.config.js         # dev 代理 /api、/uploads → 8080
│   ├── Dockerfile             # 前端镜像（Node 构建 + Nginx 托管）
│   ├── nginx.conf             # Nginx 静态托管 + 反代后端
│   └── package.json
├── docs/                      # 本文档集
├── docker-compose.yml         # 一键编排后端 + 前端
└── README.md
```

## 4. 权限模型

| 角色 | 登录入口 | 可访问范围 | 服务端约束 |
| ---- | -------- | ---------- | ---------- |
| `student` | `/`（学生端） | 仅作业提交平台 | `require_student` / `get_current_user` |
| `teacher` | `/admin`（管理端） | 作业管理 + 工作台 + 班级日志 + 系统管理 | `require_teacher` |
| `admin` | `/admin`（管理端） | 同教师 + 账号管理 | `require_teacher`（含 admin） |

**双重校验**：
- 后端：`deps.require_roles(*roles)` 依赖注入，越权返回 `403`；
- 前端：`router.beforeEach` 路由守卫，按角色重定向。

**数据隔离**：学生只能看到/提交**本班级**的作业（`homework._check_student_access`）。

**教师班级归属（班主任 + 科任）**：
- `classrooms.teacher_id` 绑定**班主任**，`class_teachers` 表关联多位**科任老师**
- 班主任与科任老师均可操作其所属班级的数据（成绩/积分/考勤/沟通/谈心/表现/评语/作业等）
- 权限判定统一走 `permissions.get_teacher_class_ids()`（返回班主任 + 科任班级）与 `is_teacher_class_owner()`（判断教师是否可操作某班）

**学生登录**：学生通过「班级 + 姓名 + 密码」登录，账号由教师创建学生档案时自动同步生成。

## 5. 数据模型概览

### 5.1 表清单（34 张表）

| 域 | 表 | 关键字段 |
| --- | --- | -------- |
| 认证 | `users` | username、password_hash、role、class_id、name |
| 基础 | `schools` / `classrooms` / `class_teachers` / `students` | 学校/班级/班级教师（班主任+科任）/学生档案（student_type 通学/寄宿） |
| 作业 | `assignments` / `assignment_attachments` / `submissions` / `submission_comments` / `excellent_works` / `work_comments` | 任务/任务附件（一对多）/提交/提交点评/优秀/评论 |
| 工作台 | `scores` / `leaves` / `attendance` / `points` / `communications` / `resources` / `exams` / `seats` / `settings` / `student_profile_tags` / `weekly_reports` / `student_board_history` | 成绩/请假/考勤点名/积分/沟通/资源/试卷/座位/设置/画像标签/周报/住宿历史 |
| 日志 | `work_logs` / `class_plans` / `teacher_plans` / `schedules` / `activities` / `talks` / `return_records` / `performances` / `student_comments` | 日志/计划/课表/活动/谈心/返校/表现/评语 |
| 审计 | `operation_logs` | 操作审计日志（含 class_id 班级维度） |
| 导入 | `import_history` | 数据导入历史（类型/文件名/成功/失败/错误详情） |

### 5.2 关键关联

- `points.performance_id` → `performances.id`：积分关联表现记录，可实现积分追溯
- `students.class_id` → `classrooms.id`：学生归属班级
- `class_teachers.class_id + teacher_id` → 班级-教师多对多关联（科任老师，班主任由 `classrooms.teacher_id` 绑定）
- `users.class_id + users.name` → 学生账号唯一标识（取代原 username 唯一约束）
- `import_history.user_id` → `users.id`：导入操作人追溯

> 说明：模型大多**不定义 ORM relationship**，关联查询通过 `db.get()` / `filter()` 手动完成，以避免模块间循环 import；唯一例外是同文件内的 `Assignment ↔ AssignmentAttachment`（一对多，用 `relationship` + `cascade="all, delete-orphan"` 实现附件级联删除）。

## 6. API 约定

- **前缀**：`/api`
- **认证**：`Authorization: Bearer <token>`（`HTTPBearer`）
- **响应**：成功返回 JSON 对象或 `{items, total}`；错误用 `HTTPException`（`{detail: ...}`）
- **分页**：`?page=&page_size=`（默认 20），`keyword` / `class_id` / `student_id` 等过滤
- **文件**：`POST /api/uploads` 上传 → 返回 `{url, filepath, filename, size}`；`/uploads/**` 静态访问
- **文件上传**：试卷上传 `POST /api/exams/upload`（FormData），下载 `GET /api/exams/{id}/download`
- **批量导入**：`POST /api/students/import` / `POST /api/scores/import`（FormData），含模板下载
- **文档**：`/docs`（Swagger UI）、`/redoc`

## 7. 前端架构

### 7.1 布局系统

- **AdminLayout**：深色可折叠侧边栏（220px ↔ 64px）+ 顶部面包屑 + 用户菜单
- **StudentLayout**：顶部导航栏 + 居中内容区 + 底部页脚
- **MobileLayout**：移动端底部 TabBar（首页/考勤/学生/记录/请假），基于 Vant
- 全局 CSS 变量系统：品牌色、中性色、阴影、圆角、间距统一管理

### 7.2 组件复用

| 组件 | 用途 | 使用页面 |
| ---- | ---- | ---- |
| `Markdown.vue` | Markdown 渲染（marked + DOMPurify） | 作业审阅、优秀作品 |
| `MarkdownEditor.vue` | Markdown 编辑器 | 作业创建/编辑 |
| `StudentSelect.vue` | 学生下拉选择器 | 积分、表现、成绩、谈心等 |

### 7.3 移动端（`/m`）

- 独立移动端 H5（Vant 4），与桌面端（Element Plus）共存，通过路由前缀 `/m` 区分
- 复用后端接口与权限体系（班主任/科任隔离、退学/毕业拦截），新增 `/api/mobile/*` 轻量接口

### 7.4 数据可视化

- ECharts 用于数据看板（折线图、饼图）和学生管理（通宿生环形图）
- 图表支持点击交互（通宿生图点击跳转明细）

## 8. 部署架构

### 开发环境
```
浏览器 → Vite(:5173) ──/api,/uploads──▶ FastAPI(:8080) ──▶ SQLite(techhub.db)
```

### Docker 部署（推荐）
```
docker compose up -d --build
浏览器 → Nginx(:80，frontend 容器)
         ├── /            → 前端静态产物(dist/)
         └── /api、/uploads → backend 容器(FastAPI :8080) ──▶ SQLite(数据卷) / MySQL
```
- `frontend` 容器：多阶段构建（Node 打包 → Nginx 托管），反代 `/api`、`/uploads` 到 `backend` 服务
- `backend` 容器：`docker-entrypoint.py` 启动时先 `alembic upgrade head` 迁移，再按需 seed，最后起 uvicorn
- SQLite 持久化在 `techhub-data` 卷，上传文件持久化在 `techhub-uploads` 卷
- 切换 MySQL/PostgreSQL 只需改 `DATABASE_URL` 环境变量

### 生产环境（裸机，可选）
```
浏览器 → Nginx(:80)
         ├── /            → 前端静态产物(dist/)
         ├── /api、/uploads → uvicorn(多 worker, :8080)
         └── HTTPS 证书终止
```
- 数据库迁移到 MySQL/PostgreSQL（SQLAlchemy 连接串切换即可）
- 使用 `gunicorn -k uvicorn.workers.UvicornWorker` 多进程部署

## 9. 数据库迁移策略

- **Alembic 为 schema 唯一来源**：`alembic upgrade head` 一次性完成建表/加列/加索引
- 本地启动 `main.py` 时执行 `run_migrations()`（`alembic upgrade head`，失败即抛错 fail-fast）；**不再**用 `create_all` 兜底建表，避免与 Alembic 交叉导致版本号/表结构不一致
- Docker 启动由 `docker-entrypoint.py` 显式先跑 `alembic upgrade head`，再按需 seed
- 模型变更必须配套新增 Alembic revision（`backend/alembic/versions/`），保证「迁移链 = 模型 schema」
- 新增字段/表后，用 `alembic revision --autogenerate` 生成迁移脚本并人工核对

## 10. 关键设计决策（ADR 摘要）

| 决策 | 选择 | 理由 |
| ---- | ---- | ---- |
| 后端框架 | FastAPI（弃用原 Express） | 原生 OpenAPI、类型提示、异步支持 |
| 前端框架 | Vue3（弃用原 React） | 与班级日志系统一致，Element Plus 生态成熟 |
| ORM 尽量无 relationship | 手动查询 | 避免循环 import，换取模型文件解耦（仅同文件的 Assignment↔Attachment 用 relationship） |
| 数据库 | SQLite | 单文件易备份，满足单校规模；预留迁移路径 |
| 认证 | JWT + bcrypt | 无状态、前后端分离友好 |
| 密码哈希 | bcrypt（弃用 passlib） | 规避 passlib/bcrypt 4.x 兼容问题 |
| 学生账号 | 班级+姓名 定位 | 解决重名问题，支持自助注册 |
| 积分联动 | 表现创建时自动生成积分 | 减少重复录入，积分可追溯 |
| 文件管理 | 试卷上传独立接口 | 格式校验、分块写入、大小限制 |
| 批量导入 | openpyxl + 逐行校验 | 精确错误定位，导入历史可追溯 |