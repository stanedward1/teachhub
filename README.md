# TeachHub

> 教学与班主任一体化工作平台 —— 一个账号，四种身份，覆盖「上机作业提交、班级日志、教师工作台」三大场景。

TeachHub 将**上机作业提交平台**、**班级日志管理系统**、**教师工作台**三个项目合并重构为**一套前后端分离**的应用，统一使用 **FastAPI + Vue 3** 技术栈，实现清晰的**角色权限隔离**。

## 文档导航

| 文档 | 说明 |
| ---- | ---- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构设计：技术栈、目录结构、权限模型、数据模型、多租户隔离、部署架构、可观测性、设计决策 |
| [docs/API.md](docs/API.md) | 接口文档：全量后端接口清单（138 条业务接口 + 运维端点，方法 + 路径 + 权限 + 约定） |
| [docs/ER-DIAGRAM.md](docs/ER-DIAGRAM.md) | 数据库 ER 图：全量 34 张表、外键删除策略分层、软关联说明 |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | 开发规范：环境搭建、代码规范、权限与多租户隔离规范、Git 规范、测试规范、发布流程 |

## 核心特性

### 角色与权限

| 角色 | 登录入口 | 可访问范围 |
| ---- | -------- | ---------- |
| 学生 `student` | 学生端 `/`（选择学校 → 班级 + 姓名） | 上机作业提交平台（查看/提交作业、优秀作品、编程练习、个人资料） |
| 教师 `teacher` | 管理端 `/admin`（选择学校 → 用户名） | **自己所属班级（班主任或科任）**：学生/成绩/积分/考勤/沟通/谈心/表现/评语/课表/活动/座位/周报 + 上机作业 + 班级日志 |
| 学校管理员 `school_admin` | 管理端 `/admin` | **本校全部**班级 + 学生 + 系统管理（班级/账号 CRUD + 年级升级 + 班级教师配置） |
| 平台超管 `super_admin` | 管理端 `/admin`（独立用户名） | **跨学校**：学校开通/启停、全局概览、所有租户数据 |

> 多租户：每所学校是独立租户，通过 `school_id` 在**接口层 + ORM 层**双重隔离，跨校访问一律返回 404/403。

学生账号**无法**访问后台接口（返回 403），权限在前后端双重校验。

### 🏫 班级权限模型（班主任 + 科任老师）

- 每个班级通过 `classrooms.teacher_id` 绑定一位**班主任**，并通过 `class_teachers` 表关联多位**科任老师**
- 班主任与科任老师在**学生管理、成绩、积分、考勤、家校沟通、谈心、返校、表现、评语、课表、活动、座位、周报、看板、作业提交**中，均可查看/操作**自己所属班级**的数据
- 教师只能查看/批改自己所属班级的作业与提交，并可查看**未交名单**（应交/已交/未交，用于催交）；管理员可查看所有班级的作业与提交
- 教师不能修改其他教师/管理员的姓名、角色、班级归属，不能重置其密码、删除其账号
- 账号管理与数据看板对教师展示**班主任/科任身份标识**；审计日志按「管理员全部 / 班主任本班 / 科任不可见」分级
- 管理员拥有全部权限，可管理所有班级和学生，并可给班级配置班主任与科任老师

### 🎯 班级联动筛选

所有学生相关模块（成绩/考勤/积分/沟通/谈心/返校/表现/评语）支持**两级联动筛选**：
- 工具栏：**先选班级 → 学生下拉只显示该班学生 → 列表按班级过滤**（可再选学生精确到个人）
- 新增/编辑对话框：同样支持"先选班级 → 再选学生"，选班级后自动清空已选学生

### 三大功能模块

**1. 上机作业提交平台（学生端）**
- 学生登录（班级 + 姓名 + 密码）/ 自助注册
- 查看教师布置的 Markdown 任务，截止时间提醒；任务附件（多个）在线下载
- 提交作业：Markdown 即时渲染编辑器 + 附件上传
- 优秀作品墙：教师评选优秀作品，学生互评，分页展示
- 编程练习推荐：热门 OJ 平台 + C 语言入门教程
- 个人资料：头像上传、密码修改

**2. 教师工作台（管理端）**
- 数据看板：核心指标卡片（可点击跳转对应模块）+ 请假趋势图（详情含班级+姓名）+ **成绩分布饼图（可按考试名称切换）** + 请假人员详情 + 班级动态（**教师视角仅统计自己班级**）
- 学生管理：通学生/寄宿生统计图表（点击查看明细）+ 批量导入导出 + 密码管理 + 头像上传（**仅自己班级**）
- 学生画像：四维雷达图（学业/品德/出勤/技能，含评价依据说明）+ 成绩趋势 + 积分历程 + 个性化标签 + 住宿状态变更历史
- 成绩管理：录入/编辑/批量导入导出 + 排序 + **按班级联动筛选**
- 考勤管理：**每日点名打卡**（出勤/缺勤/请假/迟到）+ 请假登记销假 + **出勤率统计看板**（近 7/30 天、按班级拆分）+ 积分管理（关联学生表现自动联动）+ 家校沟通、资源管理
- 试卷管理：文件上传（.pdf/.docx）+ 下载 + 在线管理
- 班级报告：数据聚合 + Markdown 模板 + 预览 + 历史归档
- 座位表：可视化排座（**教师仅可排自己班级**）

**3. 班级日志（管理端）**
- 班主任工作日志（Markdown 编辑，教师仅看自己的日志）
- 班级/教师计划总结、课程表（**仅自己班级**）
- 班级活动、师生谈心、返校记录（**仅自己班级学生**）
- 学生表现（含积分）：积极/消极记录 + 积分自动联动 + **筛选范围内积分汇总**（**仅自己班级**）
- 学生评语（**仅自己班级**，支持班级联动筛选）
- 系统设置：学期配置、年级升级（仅管理员）

**4. 通用特性**
- 所有列表页支持时间排序（最新在前/最早在前），排序偏好持久化
- 数据导入历史可追溯（含错误详情）
- 操作审计日志：**覆盖管理端全部 60+ 种写操作**（含操作人/角色/对象/班级/详情/时间），支持**按日期、操作类型、学生姓名**筛选；**权限分级**——管理员可见全部，班主任可见自己班级，科任老师不可见

### 🔐 账号安全策略
- **首次登录强制改密**：新创建/重置密码的账号首次登录后必须修改密码才能使用
- **密码强度校验**：至少 8 位，须同时包含字母和数字，不能全为相同字符
- **登录失败锁定**：连续 5 次密码错误锁定账号 15 分钟（返回 423）
- **登录限流**：登录 5 次/分钟、注册 10 次/分钟（slowapi，返回 429）

### 📱 移动端（独立 H5，Vant）
- **独立移动端**（`/m`）：班主任/管理员专用，底部 TabBar 五个入口——首页、考勤、学生、记录、请假
- 功能：学生速查与画像概览（四维雷达）、考勤打卡、快捷记录（表现/谈心）、请假登记与销假
- 管理端侧边栏在窄屏自动变为**抽屉式菜单**（点击汉堡按钮滑出 + 遮罩）
- 学生端导航自适应（窄屏隐藏文字、超小屏横向滚动）
- 全局：表格横向滚动、对话框近全屏、分页居中换行、工具栏控件全宽

### 📝 上机作业评优与点评
- 教师端提交列表**固定高度截断**展示作业内容，点击"查看详情"进入完整页面
- 详情页展示完整作业 + **教师点评区**（评语 + 可选评分 0-100 + 删除点评）
- 学生提交后教师可逐份点评，学生端可见
- **学生端反馈闭环**：「我的提交」每行可进入**提交详情页**，查看完整内容、教师批改点评（含分数与点评人）与评优评选评语；作业详情页在提交后直接展示「教师反馈」卡片

### 🖼️ 图文混排与详情纵览
- **家校沟通 / 工作日志 / 计划总结 / 班级活动 / 师生谈心** 五大模块统一使用 Markdown 图文混排编辑，**图片可插入正文任意位置**
- 五个模块列表均支持「查看」弹窗，用 Markdown 渲染全文与图片，纵览完整内容

### 🧩 平台治理能力
- **平台注册总开关**（平台超管）：管理端「系统 → 平台设置」一键开启/关闭全平台学生自助注册。关闭后 ① 后端注册接口返回 403；② 学生登录页**不再展示**「学生注册」入口。开关保存失败自动回滚界面状态
- **数据看板异常预警**：自动聚合三类可行动洞察——连续缺勤（近 7 天缺勤 ≥ 3 次）、成绩骤降（较上次下降 ≥ 20 分）、待处理请假（未销假），按类别着色展示
- **操作审计产品化**：审计日志页顶部提供「教师行为统计」（教师活跃度 Top、操作类型分布、近 30 天日趋势），从"后台排查"升级为"行为洞察"
- **可观测性**：访问日志落盘 `backend/logs/teachhub.log`（按天滚动保留 30 天，慢请求 ≥1s 标注 `[SLOW]`），并提供 Prometheus 格式的 `/metrics` 端点

## 技术栈

| 层级 | 技术 | 版本 |
| ---- | ---- | ---- |
| 后端框架 | FastAPI | 0.115 |
| ORM | SQLAlchemy | 2.0 |
| 数据库 | MySQL（生产默认）｜兼容 SQLite / MariaDB / PostgreSQL | — |
| 数据库迁移 | Alembic | 1.13 |
| 认证 | JWT（PyJWT）+ bcrypt + 登录限流（slowapi） | — |
| 前端框架 | Vue 3（Composition API） | 3.4 |
| 构建工具 | Vite | 5.4 |
| UI 组件库 | Element Plus（桌面端） | 2.7 |
| 移动端组件库 | Vant | 4.10 |
| 数据可视化 | ECharts | 5.5 |
| Markdown | marked + DOMPurify（XSS 防护） | 12 |
| Excel 处理 | openpyxl | 3.1 |
| 测试 | pytest + FastAPI TestClient | — |
| 部署 | Docker + Nginx | — |

## 项目结构

```
teachhub/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── main.py             # 应用入口（路由挂载、CORS、迁移、租户中间件）
│   │   ├── config.py           # 配置（pydantic-settings + .env 绝对路径加载，env 驱动）
│   │   ├── pagination.py       # 单查询分页（COUNT(*) OVER () 一次往返取「数据 + 总数」）
│   │   ├── logging_config.py   # 结构化日志（X-Request-ID 透传 + RequestIdFilter + StructuredFormatter）
│   │   ├── database.py         # SQLAlchemy 连接 + Alembic 迁移
│   │   ├── security.py         # JWT + bcrypt 密码哈希
│   │   ├── deps.py             # 依赖注入（角色权限 + 停用学校拦截）
│   │   ├── tenant.py           # 多租户核心：ORM 层 school_id 自动隔离
│   │   ├── permissions.py      # 班级权限 + 租户辅助（班主任/科任 + 管理员）
│   │   ├── schemas.py          # Pydantic 校验模型
│   │   ├── utils.py            # 工具函数（to_dict / gen_student_no / normalize_page）
│   │   ├── audit.py            # 操作审计日志 + 批量查询
│   │   ├── platform_settings.py# 平台级全局配置（school_id IS NULL 作用域）
│   │   ├── observability.py    # 可观测性：访问日志中间件 + /metrics（Prometheus）
│   │   ├── seed.py             # 假数据种子（默认校 + 第二校，多租户）
│   │   ├── cleanup.py          # 级联清理（purge_student_data / purge_user_data）
│   │   ├── models/             # 数据模型（按域分组，34 张表）
│   │   │   ├── user.py         #   User
│   │   │   ├── school.py       #   School / Classroom / ClassTeacher / Student
│   │   │   ├── refresh_token.py #  RefreshToken（刷新令牌：轮换 + 撤销，仅存 sha256 摘要）
│   │   │   ├── homework.py     #   Assignment / AssignmentAttachment / Submission / ExcellentWork / WorkComment / SubmissionComment
│   │   │   ├── workbench.py    #   Score / Leave / Communication / Resource / Exam / Seat / Setting / ImportHistory / StudentProfileTag / WeeklyReport / StudentBoardHistory
│   │   │   ├── classlog.py     #   WorkLog / ClassPlan / TeacherPlan / Schedule / Activity / Talk / ReturnRecord / Performance / StudentComment
│   │   │   └── operation_log.py
│   │   ├── services/           # 业务逻辑层（router 只保留装饰器/依赖/参数解析/调 service/返回）
│   │   │   ├── auth_service.py / students_service.py / classlog_service.py
│   │   │   ├── homework_service.py / admin_service.py / mobile_service.py
│   │   │   ├── meta_service.py / attendance_service.py / uploads_service.py
│   │   │   └── workbench/      #   教师工作台子域（_common + scores/leaves/communications/resources/exams/seats/imports/profile/reports）
│   │   └── routers/            # API 路由（按业务域分组，均为薄壳）
│   │       ├── auth.py         #   登录/注册/注册开关状态/密码/头像上传/学校下拉/令牌刷新/登出（含登录限流）
│   │       ├── meta.py         #   班级选项、编程练习
│   │       ├── homework.py     #   作业/提交/优秀作品/评论
│   │       ├── students.py     #   学校/班级/学生 CRUD + 导出 + 密码管理 + 通宿生统计 + 住宿历史
│   │       ├── workbench/      #   教师工作台子包（scores/leaves/communications/resources/exams/seats/imports/profile/reports）
│   │       ├── classlog.py     #   日志/计划/课表/活动/谈心/返校/表现/评语
│   │       ├── attendance.py   #   考勤点名 + 出勤率统计
│   │       ├── mobile.py       #   移动端轻量接口
│   │       ├── admin.py        #   账号管理 / 系统设置 / 数据看板 / 审计日志 / 平台概览 / 平台注册开关
│   │       └── uploads.py      #   通用文件上传
│   ├── alembic/                # 数据库迁移（schema 唯一来源，28 个 revision，head e2f3a4b5c6d7）
│   ├── logs/                   # 运行日志（teachhub.log，按天滚动保留 30 天）
│   ├── tests/                  # pytest 自动化测试（含多租户隔离）
│   ├── pytest.ini              # pytest 配置（testpaths = tests）
│   ├── clean_data.sql          # 数据清理 SQL（清空业务数据，保留账号+学校）
│   ├── repair_student_profiles.py  # 存量学生档案修复脚本
│   ├── ensure_school_admin.py      # 幂等补建学校管理员
│   ├── requirements.txt        # 运行时依赖
│   ├── requirements-dev.txt    # 开发/测试依赖（pytest、httpx）
│   ├── run.py                  # 启动脚本（端口 8080）
│   ├── Dockerfile              # 后端镜像
│   ├── docker-entrypoint.py    # 容器入口（迁移 + 首次 seed + 启动）
│   └── .env.example            # 环境变量模板
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── api/                # Axios 封装 + 接口定义
│   │   ├── router/             # 路由 + 角色守卫（四角色 + 强制改密）
│   │   ├── stores/             # Pinia 状态（auth）
│   │   ├── utils/              # 认证工具
│   │   ├── composables/        # 可组合函数（useCrudList、useSort、useDebouncedRef、useDownload、useLogout）
│   │   ├── components/         # ImportDialog（通用导入弹窗）/ Markdown / MarkdownEditor / StudentSelect（班级联动）/ StudentCard / SortBar / PaginationBar / StateView（列表四态接入层）/ SkeletonTable / ErrorState / EmptyState / VirtualList（后四者为统一体验态组件）
│   │   ├── layout/             # AdminLayout（可折叠侧边栏）/ StudentLayout；页头/菜单下沉 layout/admin/（AdminSidebar / AdminHeader / menuConfig.js）
│   │   ├── mobile/             # 移动端（Vant）：layout + views（登录/首页/学生/考勤/记录/请假/改密）+ api
│   │   └── views/              # 页面（student/ 9 个 + admin/ 29 个，含学校管理、平台设置；Students/Scores 页内子组件见 admin/students/、admin/scores/）
│   ├── vite.config.js          # /api 与 /uploads 代理 + 构建优化
│   ├── eslint.config.js        # ESLint 10（flat config）
│   ├── Dockerfile              # 前端镜像（Node 构建 + Nginx 托管）
│   ├── nginx.conf              # Nginx 配置（静态托管 + 反代后端）
│   └── package.json
├── docs/                       # 架构设计 / 接口 / ER 图 / 开发规范 / 变更日志
├── .husky/                     # Git hooks（pre-commit 跑 lint-staged；commit-msg 跑 commitlint）
├── commitlint.config.cjs       # 提交信息规范（Conventional Commits）
├── .lintstagedrc.json          # 暂存文件 lint/格式化规则
├── .gitattributes              # 换行符约定（.husky/* 强制 LF）
├── docker-compose.yml          # 一键编排后端 + 前端
├── start.sh                    # 一键启动脚本（Linux/macOS 本机）
├── stop.sh                     # 一键停止脚本（跨平台：按 PID/端口清理前后端进程）
└── README.md
```

---

## 开发环境快速开始

### 🐳 Docker 启动（最简，推荐）

无需本地安装 Python / Node / 数据库，一条命令拉起前后端：

```bash
cd teachhub
docker compose up -d --build
```

启动后：

- 前端：http://localhost （默认 `80` 端口，可用 `FRONTEND_PORT` 覆盖）
- 后端 API 文档：http://localhost:8080/docs
- 数据库：默认 SQLite，持久化在 `teachhub-data` 数据卷；上传文件持久化在 `teachhub-uploads`

**自定义配置**（可选，通过环境变量或根目录 `.env` 覆盖）：

| 变量 | 默认值 | 说明 |
| ---- | ---- | ---- |
| `FRONTEND_PORT` | `80` | 前端对外端口 |
| `DATABASE_URL` | `sqlite:////app/data/teachhub.db` | 数据库连接串，可切换 MySQL/PostgreSQL |
| `SECRET_KEY` | `teachhub-dev-secret-key` | JWT 密钥（生产必改） |
| `ENV` | `development` | `development` / `production` |
| `CORS_ORIGINS` | `http://localhost,http://127.0.0.1` | 允许跨域来源 |

> 首次启动自动执行数据库迁移，并在空库时生成演示数据（52 名学生、4 个班级等）。
> **生产环境务必设置 `ENV=production` 与强随机 `SECRET_KEY`**，否则后端会拒绝启动。

**切换 MySQL**（可选）：`docker-compose.yml` 中已内置注释掉的 `mysql` 服务与连接串示例，按注释说明三步即可切换：
1. 取消末尾 `mysql` 服务整段注释（自动创建 `teachhub` 库）
2. 将 `backend` 的 `DATABASE_URL` 改为 `mysql+pymysql://teachhub:teachhub123456@mysql:3306/teachhub?charset=utf8mb4`
3. 取消 `backend` 的 `depends_on: mysql` 注释，让后端等待 MySQL 就绪

常用命令：

```bash
docker compose up -d --build   # 构建并后台启动
docker compose logs -f backend # 查看后端日志
docker compose down            # 停止（数据卷保留）
docker compose down -v         # 停止并删除数据卷（清空数据）
```

### 🚀 一键启动（Linux 本机）

项目根目录提供 `start.sh` 一键脚本，自动完成：**架构检测（x86_64 / arm64）→ 安装系统依赖与 Node.js → 初始化数据库（默认 SQLite，可切 MySQL）→ 安装后端依赖（阿里云镜像）→ 安装前端依赖（npmmirror 镜像）→ 数据库迁移与首次 seed → 启动前后端服务**。

```bash
cd teachhub

# 一键启动（首次运行会自动安装全部依赖，约 5-10 分钟）
./start.sh

# 仅安装依赖、不启动服务（适合先准备环境）
./start.sh --install-only
```

启动完成后：
- 前端：http://localhost:5173 （局域网设备用 `http://<本机IP>:5173/`）
- 后端 API 文档：http://localhost:8080/docs
- 健康检查 / 指标：http://localhost:8080/health 、 http://localhost:8080/metrics
- 运行日志：`backend/logs/teachhub.log`（按天滚动，保留 30 天；`tail -f backend/logs/teachhub.log` 实时查看）
- 数据库：默认 **SQLite**（`backend/teachhub.db`，零配置）；如需 MySQL/MariaDB，运行 `DB_ENGINE=mysql bash start.sh` 并在 `start.sh` 顶部配置账号密码

停止服务（跨平台，按进程/端口清理）：

```bash
./stop.sh              # 停止前后端
./stop.sh backend      # 仅停止后端
./stop.sh frontend     # 仅停止前端
```

> **说明**：`start.sh` 自动检测 CPU 架构（x86_64 / arm64）、安装系统依赖与 Node.js 20、
> 创建 Python 虚拟环境、生成 `.env`、执行数据库迁移（Alembic）与首次 seed、最后启动前后端；
> 前端 node_modules 平台差异（x86/ARM esbuild 原生二进制）自动修复。

### 环境要求

| 工具 | 最低版本 |
| ---- | -------- |
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ |
| MariaDB/MySQL | 10.4+ / 8.0+ |

### 1. 启动后端（手动方式）

```bash
cd backend

# 创建虚拟环境并安装依赖
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# （可选）运行测试需额外安装开发依赖
pip install -r requirements-dev.txt

# 复制环境变量配置（可选，开发环境有默认值）
cp .env.example .env

# 生成演示假数据（可选，首次运行建议执行）
python -m app.seed

# 启动服务（默认端口 8080，自动建表和迁移）
python run.py
```

启动后：
- API 文档：http://localhost:8080/docs
- 健康检查：http://localhost:8080/health

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173（学生端），管理后台 http://localhost:5173/admin。

### 3. 演示账号

| 账号 | 密码 | 身份 |
| ---- | ---- | ---- |
| `admin` | `admin123` | 平台超管（跨学校） |
| `school_admin` | `admin123` | 学校管理员（本校） |
| `teacher` | `123456` | 教师（默认校，班主任） |
| `teacher3` | `123456` | 教师（第二校，用于验证隔离） |
| 学生（学校 + 班级 + 姓名 + `123456`） | — | 学生 |

> 学生账号的用户名即姓名，由 seed.py 自动生成 52 名学生（默认校）+ 5 名（第二校）；也可在学生端登录页通过「学校 + 班级 + 姓名」自助注册。

---

## 生产环境部署

> **警告**：生产环境必须修改默认密钥和密码，否则存在严重安全风险。

### 环境要求

| 工具 | 最低版本 |
| ---- | -------- |
| Python | 3.10+ |
| Node.js | 18+ |
| Nginx | 1.20+ |
| 数据库 | MySQL/MariaDB 8.0+ / 10.4+（推荐，生产默认） |

### 1. 构建前端

```bash
cd frontend
npm install
npm run build          # 产物输出到 dist/ 目录
```

构建产物位于 `frontend/dist/`，包含压缩后的静态资源（JS/CSS/HTML），Vite 自动按路由拆分 chunk。

### 2. 配置后端环境变量

```bash
cd backend
cp .env.example .env
```

编辑 `.env` 文件，**生产环境必须修改以下配置**：

```env
# 环境标识
ENV=production

# 【必改】JWT 签名密钥，生成命令：python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=替换为随机生成的64位十六进制字符串

# 数据库（MySQL/MariaDB，生产推荐；也可用 SQLite 快速体验）
# 先创建数据库：mysql -u root -p -e "CREATE DATABASE teachhub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
DATABASE_URL=mysql+pymysql://root:your_password@127.0.0.1:3306/teachhub?charset=utf8mb4

# 允许跨域的前端地址（多个用逗号分隔）
CORS_ORIGINS=http://localhost,http://your-domain.com

# 文件上传大小限制（字节）
MAX_UPLOAD_SIZE=20971520
```

> **警告**：切勿使用 `SECRET_KEY` 的默认值，否则 JWT Token 可被伪造。

### 3. 安装后端依赖

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# 或 .venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 4. 初始化数据库

```bash
# 生成初始数据（可选，仅首次部署需要）
python -m app.seed

# 若不生成假数据，启动时也会自动建表
```

### 5. 启动后端服务

**方式 A：直接启动（单机小规模）**

```bash
python run.py    # 端口 8080，单进程
```

**方式 B：Gunicorn 多进程（推荐生产环境）**

```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8080 app.main:app
```

参数说明：
- `-w 4`：4 个 worker 进程（建议设为 CPU 核心数 × 2）
- `-k uvicorn.workers.UvicornWorker`：使用 Uvicorn ASGI worker
- `-b 0.0.0.0:8080`：监听所有网卡的 8080 端口

### 6. 配置 Nginx 反向代理

创建 `/etc/nginx/sites-available/teachhub`：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    root /path/to/teachhub/frontend/dist;
    index index.html;

    # 前端页面（SPA 路由支持）
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理到后端
    location /api {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 上传文件访问
    location /uploads {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
    }

    # 静态资源缓存（7 天）
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1024;
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/teachhub /etc/nginx/sites-enabled/
sudo nginx -t           # 测试配置
sudo systemctl reload nginx
```

#### 6.1 客户端 IP（说明）

> **本项目已不做客户端 IP 的记录与还原。** 原先的「最后登录 IP」功能、`_client_ip` 还原代码、
> 一度尝试的「设备识别（物理机）」功能，以及 `refresh_tokens.ip` 列（迁移 `e2f3a4b5c6d7` 删除），
> 均已按需求下线并删除（详见 `docs/CHANGELOG.md`）。

若将来确实需要记录客户端 IP，先记住一条铁律：
**客户端 IP 只有最外层那个代理知道；它没往下传，后端就永远拿不到** ——
转发客户端 IP 是**最外层代理**的责任，不是后端代码能修的 bug。

- 前端由 **Vite 开发服务器**提供时（本项目当前线上形态，无 nginx）：靠 `frontend/vite.config.js`
  的 `server.proxy`。**当前刻意不开 `xfwd`** —— 既然不再记录客户端 IP，就没有转发转发头的必要；
  将来要用时再打开（http-proxy 会附加 `X-Forwarded-For / -Proto / -Host / -Port`）。
- 前端由 **Nginx** 托管时：`location /api` 必须显式写
  `proxy_set_header X-Real-IP $remote_addr;` 与
  `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`。
### 7. 配置 HTTPS（推荐）

```bash
# 使用 Certbot 获取免费 SSL 证书
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 8. 使用 systemd 管理后端服务

创建 `/etc/systemd/system/teachhub.service`：

```ini
[Unit]
Description=TeachHub Backend
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/path/to/teachhub/backend
Environment="PATH=/path/to/teachhub/backend/.venv/bin"
ExecStart=/path/to/teachhub/backend/.venv/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8080 app.main:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable teachhub
sudo systemctl start teachhub
sudo systemctl status teachhub   # 检查运行状态
```

### 9. 验证部署

```bash
# 1. 健康检查
curl http://localhost:8080/health
# 预期返回：{"status":"ok"}

# 2. 前端页面
curl http://localhost/
# 预期返回：HTML 页面

# 3. 登录测试
curl -X POST http://localhost/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
# 预期返回：{"token":"...","refresh_token":"...","user":{...},"must_change_password":false}
```

> 访问令牌 `token` 用于后续请求的 `Authorization: Bearer <token>`；`refresh_token` 用于 `POST /api/auth/refresh` 换取新令牌对（一次性轮换），登出调 `POST /api/auth/logout`。详见 [docs/API.md](docs/API.md)。

---

## 自动化测试

```bash
cd backend
python -m pytest tests/ -v
```

测试覆盖：登录认证、权限隔离、作业流程、优秀作品评选、CRUD 操作、越权场景。

## 配置参考

| 环境变量 | 说明 | 默认值 | 生产建议 |
| ---- | ---- | ---- | ---- |
| `ENV` | 运行环境 | `development` | `production` |
| `SECRET_KEY` | JWT 签名密钥 | 开发默认值 | **必须修改**为随机 64 位 hex |
| `DATABASE_URL` | 数据库连接串 | `sqlite:///./teachhub.db` | MySQL/PostgreSQL 连接串 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 访问令牌有效期（分钟） | `1440`（24h） | 按需调整 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 刷新令牌有效期（天） | `30` | 按需调整 |
| `MAX_UPLOAD_SIZE` | 上传文件大小上限 | `20971520`（20MB） | 按需调整 |
| `CORS_ORIGINS` | 允许跨域的前端地址 | `http://localhost:5173` | 生产域名 |
| `ALGORITHM` | JWT 签名算法 | `HS256` | 保持默认 |

## 故障排除

| 问题 | 原因 | 解决方案 |
| ---- | ---- | -------- |
| 前端页面空白 | Nginx 未正确配置 SPA 路由 | 确认 `try_files $uri /index.html` 配置 |
| API 返回 500 | 数据库迁移未完成 | 重启后端，检查日志中的迁移信息 |
| 文件上传失败 | 上传目录权限不足 | `chmod 755 backend/uploads` |
| 登录后立即跳回登录页 | Token 过期或 SECRET_KEY 变更 | 清除浏览器 localStorage，重新登录 |
| 图表不显示 | ECharts DOM 未就绪 | 刷新页面，等待数据加载完成 |
| `address already in use` | 端口被占用 | 先执行 `./stop.sh` 清理残留进程；或修改 `run.py` 中的 `port` 参数 |
| 数据库文件损坏 | 异常断电 | 恢复 `teachhub.db` 备份文件 |
| 想排查接口报错/慢请求 | 需要运行日志 | 查看 `backend/logs/teachhub.log`（慢请求 ≥1s 标注 `[SLOW]`）；或抓取 `/metrics` 看耗时直方图与状态码分布 |
| 接入 Prometheus | 需要指标端点 | 将抓取目标指向 `http://<host>:8080/metrics` |
| 学生登录页没有「学生注册」入口 | 平台注册开关处于关闭状态 | 平台超管登录管理端 → 「系统 → 平台设置」打开注册开关；接口 `GET /api/auth/registration-status` 可查看当前状态 |

## License

MIT