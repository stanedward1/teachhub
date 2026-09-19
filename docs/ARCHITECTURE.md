# TeachHub 架构设计文档

> 版本：2.5 ｜ 更新：2026-09-19 ｜ 适用对象：后端 / 前端 / 测试 / 运维

## 1. 项目定位

TeachHub 是一套面向中职学校的「教学 + 班主任一体化工作平台」，将原先分散的三个系统合并为**一套前后端分离**的应用：

| 原系统 | 定位 | 合并后形态 |
| ------ | ---- | ---------- |
| 上机作业提交平台 | 学生交作业、教师评优 | **学生端**（`/`） |
| 班级日志管理系统 | 班主任班级事务 | **管理端**模块（`/admin`） |
| 教师工作台 | 教师日常教务 | **管理端**模块（`/admin`） |

**核心设计目标**：一个账号、四角色（平台超管 / 学校管理员 / 教师 / 学生）、多租户数据严格隔离。

## 2. 技术栈

| 层 | 技术 | 版本 | 说明 |
| --- | ---- | ---- | ---- |
| 后端框架 | FastAPI | 0.115 | 自动生成 OpenAPI 文档 |
| ORM | SQLAlchemy | 2.0 | 声明式模型 |
| 数据库 | MySQL | 8.0+ | 生产默认；兼容 SQLite / MariaDB / PostgreSQL |
| 迁移 | Alembic | 1.13 | schema 唯一来源，`upgrade head` 建表/加列 |
| 认证 | PyJWT + bcrypt + slowapi | — | JWT（HS256）+ bcrypt 密码哈希 + 登录限流 |
| 前端框架 | Vue 3 | 3.4 | Composition API + `<script setup>` |
| 状态管理 | Pinia | 2 | 认证状态（auth store）响应式管理 |
| UI 库 | Element Plus | 2.7 | 后台与表单（桌面端） |
| 移动端 UI 库 | Vant | 4.10 | 移动端 H5（`/m`） |
| 图表 | ECharts | 5.5 | 数据看板、通宿生统计（按需引入） |
| 构建 | Vite | 5.4 | 开发热更新 + 生产构建 |
| Markdown | marked + DOMPurify | 12 | 作业正文/日志渲染 + XSS 防护 |
| Excel | openpyxl | 3.1 | 导入/导出 |
| 代码规范 | ESLint + Prettier | 10 / 3 | flat config + 格式化 |
| 测试 | pytest | — | 后端自动化测试 |
| 部署 | Docker + Nginx | — | 多阶段镜像 + 静态托管 + 反代 |

## 3. 目录结构

```
techhub/
├── backend/
│   ├── app/
│   │   ├── main.py            # 应用入口：CORS、静态挂载、路由注册、迁移、租户中间件
│   │   ├── config.py          # 配置（pydantic-settings + .env，绝对路径加载，env 驱动）
│   │   ├── database.py        # engine / SessionLocal / Base / get_db / run_migrations
│   │   ├── security.py        # 密码哈希 + JWT 签发/校验（payload 含 school_id）
│   │   ├── deps.py            # 依赖：get_current_user / require_roles（含停用学校拦截）
│   │   ├── tenant.py          # 多租户核心：ContextVar 上下文 + ORM 层 school_id 自动隔离
│   │   ├── permissions.py     # 班级权限 + 租户辅助（is_any_admin / get_student_account 等）
│   │   ├── utils.py           # to_dict / safe_filename / gen_student_no / normalize_page
│   │   ├── audit.py           # 操作审计日志（含 school_id）+ 批量查询辅助
│   │   ├── platform_settings.py # 平台级全局配置（school_id IS NULL 作用域）：get/set_global_setting、is_registration_allowed
│   │   ├── observability.py   # 可观测性：访问日志中间件 + /metrics（Prometheus 指标，零依赖）
│   │   ├── pagination.py      # 单查询分页：paginate(db, stmt, page, page_size)（COUNT(*) OVER () 一次往返取「数据 + 总数」）
│   │   ├── logging_config.py  # 结构化日志：X-Request-ID 透传 + RequestIdFilter + StructuredFormatter + setup_logging()
│   │   ├── schemas.py         # Pydantic 请求/响应模型
│   │   ├── cleanup.py         # 级联清理（purge_student_data / purge_user_data，叶子→根拓扑倒序）
│   │   ├── models/            # SQLAlchemy 模型（按域分组）
│   │   │   ├── user.py        #   User
│   │   │   ├── school.py      #   School / Classroom / ClassTeacher / Student
│   │   │   ├── homework.py    #   Assignment / AssignmentAttachment / Submission / ExcellentWork / WorkComment / SubmissionComment
│   │   │   ├── workbench.py   #   Score / Leave / Communication / Resource / Exam / Seat / Setting / ImportHistory / StudentProfileTag / WeeklyReport / StudentBoardHistory
│   │   │   ├── classlog.py    #   WorkLog / ClassPlan / TeacherPlan / Schedule / Activity / Talk / ReturnRecord / Performance / StudentComment
│   │   │   ├── refresh_token.py #   RefreshToken（刷新令牌：轮换 + 撤销，仅存 sha256 摘要）
│   │   │   └── operation_log.py
│   │   ├── routers/           # 按业务域分组的 API 路由
│   │   │   ├── auth.py        #   登录/注册/注册开关状态/密码/学校下拉（含登录限流）
│   │   │   ├── meta.py        #   班级选项、编程练习（公开）
│   │   │   ├── homework.py    #   作业/提交/优秀作品/评论
│   │   │   ├── students.py    #   学校/班级/学生 CRUD + 班级教师（班主任+科任）+ 密码管理 + 通宿生统计
│   │   │   ├── workbench/     #   教师工作台子包（原单文件 1374 行按资源域拆分）
│   │   │   │   ├── _common.py       #   共享依赖与辅助
│   │   │   │   ├── scores.py        #   成绩 + 导入导出
│   │   │   │   ├── leaves.py        #   请假
│   │   │   │   ├── communications.py#   家校沟通
│   │   │   │   ├── resources.py     #   教学资源
│   │   │   │   ├── exams.py         #   试卷上传/下载
│   │   │   │   ├── seats.py         #   座位表
│   │   │   │   ├── imports.py       #   导入历史
│   │   │   │   ├── profile.py       #   学生画像
│   │   │   │   ├── reports.py       #   班级周报
│   │   │   │   └── __init__.py      #   聚合导出统一 router
│   │   │   ├── classlog.py    #   班级日志（日志/计划/课表/活动/谈心/返校/表现/评语）
│   │   │   ├── attendance.py  #   考勤点名 + 出勤率统计
│   │   │   ├── mobile.py      #   移动端专用接口（学生速查 + 画像概览）
│   │   │   ├── admin.py       #   账号管理 / 系统设置 / 数据看板 / 审计日志 / 平台概览 / 平台注册开关
│   │   │   └── uploads.py     #   通用文件上传
│   │   ├── services/          # 业务服务层（B1 分层）：router 只做路由/依赖/参数解析/调用/返回
│   │   │   ├── auth_service.py / students_service.py / classlog_service.py / homework_service.py / admin_service.py
│   │   │   ├── mobile_service.py / meta_service.py / attendance_service.py / uploads_service.py
│   │   │   └── workbench/     #   工作台子包：_common.py + scores/leaves/communications/resources/exams/seats/imports/profile/reports_service.py
│   │   └── seed.py            # 假数据生成（多租户：默认校 + 第二校）
│   ├── alembic/               # 数据库迁移（Alembic，schema 唯一来源，当前 23 个 revision）
│   ├── logs/                  # 运行日志（teachhub.log，按天滚动保留 30 天，不入库）
│   ├── tests/                 # pytest 自动化测试（含 test_multi_tenant.py）
│   ├── pytest.ini            # pytest 配置（testpaths = tests，仅收集 tests/）
│   ├── clean_data.sql         # 数据清理 SQL（事务包裹，清空业务数据保留账号）
│   ├── repair_student_profiles.py   # 存量学生档案修复脚本（可重复执行）
│   ├── ensure_school_admin.py       # 幂等补建默认租户学校管理员
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
│   │   ├── router/            # 路由 + 角色守卫（四角色 + 强制改密）
│   │   ├── stores/            # Pinia store（auth）
│   │   ├── layout/            # StudentLayout / AdminLayout（可折叠外壳）
│   │   │   └── admin/         #   AdminLayout 子件：AdminSidebar / AdminHeader / menuConfig.js
│   │   ├── composables/       # 可组合函数（useSort / useDebouncedRef / useSubmit / useDownload / useLogout）
│   │   ├── components/        # ImportDialog / Markdown / MarkdownEditor / StudentSelect / StudentCard / SortBar / PaginationBar / StateView（四态接入层）/ SkeletonTable / ErrorState / EmptyState / VirtualList
│   │   ├── mobile/            # 移动端（Vant）：layout + views + api
│   │   ├── views/student/     # 学生端页面（登录/作业/优秀作品/我的提交+详情/编程练习/资料）
│   │   └── views/admin/       # 管理端页面（29 个，含 Schools 学校管理、PlatformSettings 平台设置）
│   │       ├── students/      #   Students 子件：表单/密码/变更历史/饼图/头像单元格
│   │       └── scores/        #   Scores 子件：成绩分析 / 录入弹窗
│   ├── vite.config.js         # dev 代理 /api、/uploads → 8080
│   ├── eslint.config.js       # ESLint 10（flat config）
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
| `student` | `/`（学生端，选学校 → 班级 + 姓名） | 仅作业提交平台（本班） | `require_student` / `get_current_user` |
| `teacher` | `/admin`（管理端，选学校 → 用户名） | 自己负责班级（班主任 + 科任）的作业管理 + 工作台 + 班级日志 | `require_teacher` |
| `school_admin` | `/admin`（管理端） | 本校全部班级/学生/账号 + 系统管理 | `require_school_admin` |
| `super_admin` | `/admin`（管理端） | 跨学校：学校开通/启停 + 全局概览 + 所有租户数据 | `require_super_admin` |

**双重校验**：
- 后端：`deps.require_roles(*roles)` 依赖注入，越权返回 `403`；另有多租户 `school_id` 隔离（接口层 + ORM 层双重拦截）。
- 前端：`router.beforeEach` 路由守卫，按角色重定向。

**多租户数据隔离**：每所学校是独立租户，通过 `school_id` 隔离——ORM 层自动为所有查询注入 `school_id` 过滤（含 `db.get`），跨校访问返回 `None`→404；平台超管 `school_id=NULL` 不受限。

**教师班级归属（班主任 + 科任）**：
- `classrooms.teacher_id` 绑定**班主任**，`class_teachers` 表关联多位**科任老师**
- 班主任与科任老师均可操作其所属班级的数据（成绩/积分/考勤/沟通/谈心/表现/评语/作业等）
- 权限判定统一走 `permissions.get_teacher_class_ids()`（返回班主任 + 科任班级，限定本校）与 `is_teacher_class_owner()`（判断教师是否可操作某班）

**学生登录**：学生通过「学校 + 班级 + 姓名 + 密码」登录，账号由教师创建学生档案时自动同步生成。

**认证与令牌刷新（F3）**：
- 登录返回短期 `access token`（JWT，payload 含 `school_id`）+ 长期 `refresh_token`（明文仅返回一次，库中存 sha256 摘要于 `refresh_tokens` 表，含 `school_id` 归属、`expires_at`；有效期 `REFRESH_TOKEN_EXPIRE_DAYS`，默认 30 天）。
- `POST /api/auth/refresh`：用 `refresh_token` 做**一次性轮换**——签发新 access + 新 refresh，旧行置 `revoked_at` 并记 `replaced_by`；未命中 / 已撤销 / 已过期一律返回 `401 {"detail":"登录已过期，请重新登录"}`（无需鉴权）。
- `POST /api/auth/logout`：幂等撤销（令牌不存在也返回成功）。
- 登录响应在原有 `token` / `user` / `must_change_password` 基础上**新增** `refresh_token`，原字段不变。
- 前端：`request.js` 对非登录接口的 `401` 做**单飞静默刷新**并重放原请求一次，刷新失败才跳登录。登出统一走 `composables/useLogout.js`（先撤销服务端刷新令牌，再清理本地登录态并跳登录页）。

## 5. 数据模型概览

### 5.1 表清单（34 张表）

| 域 | 表 | 关键字段 |
| --- | --- | -------- |
| 认证 | `users` / `refresh_tokens` | users：username、password_hash、role、school_id、class_id、name；refresh_tokens：user_id、school_id、token_hash、expires_at、revoked_at、replaced_by |
| 基础 | `schools` / `classrooms` / `class_teachers` / `students` | 学校（status 启用/停用）/班级/班级教师（班主任+科任）/学生档案（student_type 通学/寄宿） |
| 作业 | `assignments` / `assignment_attachments` / `submissions` / `submission_comments` / `excellent_works` / `work_comments` | 任务/任务附件（一对多）/提交/提交点评/优秀/评论 |
| 工作台 | `scores` / `leaves` / `attendance` / `communications` / `resources` / `exams` / `seats` / `settings` / `student_profile_tags` / `weekly_reports` / `student_board_history` | 成绩/请假/考勤点名/沟通/资源/试卷/座位/设置/画像标签/周报/住宿历史 |
| 日志 | `work_logs` / `class_plans` / `teacher_plans` / `schedules` / `activities` / `talks` / `return_records` / `performances` / `student_comments` | 日志/计划/课表/活动/谈心/返校/表现/评语 |
| 审计 | `operation_logs` | 操作审计日志（含 class_id 班级维度） |
| 导入 | `import_history` | 数据导入历史（类型/文件名/成功/失败/错误详情） |

> 说明：原独立的 `points` 积分表已并入 `performances`（新增 `points` 数值列承载积分语义），积分/画像/周报统计统一基于 `performances.points` 聚合，总分口径 `BASE_POINTS(100) + sum(points)`。

### 5.2 关键关联

- `performances.points` → 积分语义列（正数加分/负数减分，默认 ±1）；学生表现与积分合并为同一业务
- `students.class_id` → `classrooms.id`：学生归属班级
- `class_teachers.class_id + teacher_id` → 班级-教师多对多关联（科任老师，班主任由 `classrooms.teacher_id` 绑定）
- `users.school_id + class_id + name` → 学生账号唯一标识（取代原 username 唯一约束；教师用户名按 `school_id + username` 校内唯一）
- `settings.school_id + key` → 系统设置校内唯一（多租户下不同学校可设置同名配置项）
- `settings` 的**平台级全局配置**：`school_id IS NULL` 的行表示跨校全局配置（如 `allow_registration` 注册总开关），读写统一走 `app/platform_settings.py`，与校内配置（`school_id = 本校`）互不干扰
- `import_history.user_id` → `users.id`：导入操作人追溯

### 5.3 外键删除策略（分层）

外键共 40 个，按语义分层设置 `ondelete` 删除规则：

- **CASCADE（16 个，纯从属关系）**：作业链（`assignment_attachments`/`submissions`→`assignments`、`excellent_works`/`submission_comments`→`submissions`、`work_comments`→`excellent_works`）+ 学生业务链（`scores`/`attendance`/`leaves`/`performances`/`communications`/`talks`/`return_records`/`student_comments`/`student_profile_tags`/`student_board_history`/`submissions`→`students`）。删父记录自动级联删子记录。
- **RESTRICT（24 个，归属/操作人关系）**：`classrooms.teacher_id`、`class_teachers.teacher_id`、`assignments.created_by`、`excellent_works.selected_by`、各日志表的 `teacher_id`/`created_by`/`changed_by` 等，以及所有 `school_id`/`class_id` 引用。删归属主体时保留业务数据，由应用层显式处理。
- **代码双保险**：`cleanup.py` 的 `purge_student_data`/`purge_user_data` 按「叶子→根」拓扑倒序先删子表再删父表，与 DB CASCADE 兼容（先显式清空，CASCADE 无副作用）。

> 说明一：模型大多**不定义 ORM relationship**，关联查询通过 `db.get()` / `filter()` 手动完成，以避免模块间循环 import；唯一例外是同文件内的 `Assignment ↔ AssignmentAttachment`（一对多，用 `relationship` + `cascade="all, delete-orphan"` 实现附件级联删除）。

> 说明二（`student_id` 语义统一）：所有业务表的 `student_id` 均指向 `students.id`（学生档案），包括 `submissions` / `scores` / `talks` / `performances` / `leaves` / `communications` / `return_records` / `student_comments` / `attendance` / `student_board_history` / `student_profile_tags`。学生登录账号（`users.id`）与学生档案通过「`class_id + name`」关联，由 `permissions.get_student_by_account()` 定位。

## 6. API 约定

- **前缀**：`/api`
- **认证**：`Authorization: Bearer <token>`（`HTTPBearer`）
- **响应**：成功返回 JSON 对象或 `{items, total}`；错误用 `HTTPException`（`{detail: ...}`）
- **分页**：`?page=&page_size=`（默认 20），`keyword` / `class_id` / `student_id` 等过滤
- **文件**：`POST /api/uploads` 上传 → 返回 `{url, filepath, filename, size}`；`/uploads/**` 静态访问
- **文件上传**：试卷上传 `POST /api/exams/upload`（FormData），下载 `GET /api/exams/{id}/download`
- **批量导入**：`POST /api/students/import` / `POST /api/scores/import`（FormData），含模板下载
- **公开接口**：`/api/auth/login`、`/api/auth/register`、`/api/auth/registration-status`（注册开关状态）、`/api/auth/schools`、`/api/meta/*`
- **令牌刷新 / 登出（无需鉴权）**：`POST /api/auth/refresh`（refresh token 轮换）、`POST /api/auth/logout`（幂等撤销）
- **运维端点**：`/health`（健康检查）、`/metrics`（Prometheus 指标）
- **文档**：`/docs`（Swagger UI）、`/redoc`

## 7. 前端架构

### 7.1 布局系统

- **AdminLayout**：深色可折叠侧边栏（220px ↔ 64px）+ 顶部面包屑 + 用户菜单；外壳（`el-aside` / `el-header` / 盒子样式）留在 `AdminLayout.vue`，菜单与页头下沉 `layout/admin/`（`AdminSidebar` / `AdminHeader` / `menuConfig.js` 数据驱动）。**注意**：`el-container` 靠直接子节点组件名推断 flex 方向，外壳容器不得再下沉。
- **StudentLayout**：顶部导航栏 + 居中内容区 + 底部页脚
- **MobileLayout**：移动端底部 TabBar（首页/考勤/学生/记录/请假），基于 Vant
- 全局 CSS 变量系统：品牌色、中性色、阴影、圆角、间距统一管理

### 7.2 组件复用

| 组件 | 用途 | 使用页面 |
| ---- | ---- | ---- |
| `Markdown.vue` | Markdown 渲染（marked + DOMPurify 防 XSS） | 作业审阅、优秀作品、五大图文模块的详情弹窗 |
| `MarkdownEditor.vue` | Markdown 图文混排编辑器（`rows` / `height` 可配） | 作业创建、家校沟通、工作日志、计划总结、班级活动、师生谈心 |
| `StudentSelect.vue` | 学生下拉选择器 | 表现、成绩、谈心、请假等 |
| `StudentCard.vue` | 学生信息卡片 | 学生列表/画像 |
| `SortBar.vue` | 列表排序控件（最新/最早，偏好持久化） | 各业务列表页 |
| `PaginationBar.vue` | 统一分页条（居中换行、窄屏自适应） | 各业务列表页 |
| `ImportDialog.vue` | 通用 Excel 批量导入弹窗（模板下载 + 拖拽上传 + 错误明细；业务差异由 `importFn` / `templateUrl` 注入） | 学生管理、成绩管理 |
| `StateView.vue` | **列表四态接入层**：组合「骨架屏 / 错误+重试 / 空态 / 正常内容」，页面只传 `loading` / `error` / `empty` 三个布尔量；支持 `#skeleton` 具名插槽自定义骨架、`#empty` 插槽放操作按钮 | 全部 27 处列表视图（管理端 23 页 + 成绩分析页签 + 学生端 3 页） |
| `SkeletonTable.vue` | 表格加载骨架屏（表头 + 若干行占位，行高固定防 CLS）；多由 `StateView` 间接使用 | 各列表页 |
| `ErrorState.vue` | 统一错误态（含「重试」按钮，向上抛 `retry`）；多由 `StateView` 间接使用 | 各列表页 |
| `EmptyState.vue` | 统一空状态占位（默认插槽可放「新建」等按钮）；多由 `StateView` 间接使用 | 各列表页 |
| `VirtualList.vue` | 长列表虚拟滚动（固定行高窗口化，`requestAnimationFrame` 节流，DOM 节点数恒定） | 移动端「快捷记录」选学生弹窗（全校长列表） |

> **P1 已全量落地**：四态接入层 `StateView` 及其三个原语组件（空 / 错误 / 骨架屏）已接入全部 27 处列表视图，`VirtualList` 接入移动端全校长列表。约定页面把 `<el-table>`（或自绘列表）包进 `<StateView ... @retry="load">`，并在 `load()` 中按「先 `loading = true`，再 `error = false`；`catch` 置 `error = true`」改造；**骨架屏与错误态只在首屏出现**，后续翻页/搜索刷新保留已有内容（仍由 `v-loading` 反馈）。
>
> 例外：`Schedules.vue` 的课表网格不接空态（空网格是「点 + 号加课」的交互入口）；Dashboard / `StudentProfile` / `WeeklyReport` 用 `#skeleton` 自定义骨架（图表页不适用表格骨架）。

> 巨型页面组件（`Students.vue` / `Scores.vue`）已按职责拆为「编排层 + 页内子组件」：编排层保留列表/分页/取数，子组件下沉同目录子文件夹（`views/admin/students/`、`views/admin/scores/`），子组件仅在本页复用、不提升为全局 `components/`。

> 五大图文模块（家校沟通 / 工作日志 / 计划总结 / 班级活动 / 师生谈心）统一采用「`MarkdownEditor` 图文混排编辑 + `Markdown` 详情弹窗纵览」的交互形态，图片以 `![图片](url)` 内嵌于正文任意位置。

### 7.3 移动端（`/m`）

- 独立移动端 H5（Vant 4），与桌面端（Element Plus）共存，通过路由前缀 `/m` 区分
- 复用后端接口与权限体系（班主任/科任隔离、退学/毕业拦截），新增 `/api/mobile/*` 轻量接口

### 7.4 数据可视化

- ECharts 用于数据看板（折线图、饼图）和学生管理（通宿生环形图）
- 图表支持点击交互（通宿生图点击跳转明细）

## 8. 部署架构

### 开发环境
```
浏览器 → Vite(:5173) ──/api,/uploads──▶ FastAPI(:8080) ──▶ MySQL(teachhub)
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
- SQLite 持久化在 `teachhub-data` 卷，上传文件持久化在 `teachhub-uploads` 卷
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

## 10. 可观测性

- **访问日志中间件**（`app/observability.py`）：最外层 HTTP 中间件，结构化记录每个请求的 `方法 + 路径 + 状态码 + 耗时`；耗时 ≥ 1s 的慢请求提升到 WARN 级别并附加 `[SLOW]` 标记，便于日志采集系统（ELK / Loki）快速定位。
- **请求链路 ID（`X-Request-ID`）**：中间件读入站 `X-Request-ID` 请求头（缺失则生成 `uuid4`）并写回响应头，每条日志行统一前缀 `[rid=...]`，便于把同一请求的多条日志在 ELK / Loki 中串联。
- **结构化日志（`app/logging_config.py`）**：`RequestIdFilter` 把当前 request-id 注入日志记录，`StructuredFormatter` 统一输出格式；`setup_logging()` 取代 `logging.basicConfig` 统一初始化 handler。
  - ⚠️ 文件 handler 仍**必须**在 `run_migrations()` 之后初始化——Alembic 会重置 root logger 的 handler，先挂会被清空（既有坑，务必保留）。
- **`/metrics` 端点**：输出 Prometheus 文本格式，聚合以下指标（进程内内存计数，零第三方依赖）：
  - `teachhub_http_requests_total`：累计请求数（按路径）
  - `teachhub_http_status_total`：响应状态码分布
  - `teachhub_http_duration_seconds_bucket`：请求耗时直方图（分桶，按路径）
  - `teachhub_slow_requests_total`：慢请求（≥1s）计数
  - `teachhub_inflight_requests`：当前进行中的请求数（gauge）
- **接入方式**：Prometheus 抓取 `/metrics`，Grafana 可视化。单实例部署下内存计数即可满足；多副本横向扩展时，应改用 Redis 共享计数或接入 `prometheus-fastapi` + 独立 exporter。

## 11. 关键设计决策（ADR 摘要）

| 决策 | 选择 | 理由 |
| ---- | ---- | ---- |
| 后端框架 | FastAPI（弃用原 Express） | 原生 OpenAPI、类型提示、异步支持 |
| 前端框架 | Vue3（弃用原 React） | 与班级日志系统一致，Element Plus 生态成熟 |
| ORM 尽量无 relationship | 手动查询 | 避免循环 import，换取模型文件解耦（仅同文件的 Assignment↔Attachment 用 relationship） |
| 数据库 | MySQL（生产默认，兼容 SQLite） | 强制外键约束暴露级联缺陷；SQLite 作零配置开发/单机备选 |
| 认证 | PyJWT + bcrypt + slowapi | 无状态、前后端分离友好；弃用已停维的 python-jose；登录限流防爆破 |
| 密码哈希 | bcrypt（弃用 passlib） | 规避 passlib/bcrypt 4.x 兼容问题 |
| 状态管理 | Pinia | 用户信息响应式，替代 localStorage 反复解析 |
| 积分与表现合并 | performances 加 points 列 | 消除重复建模（90% 语义重叠），统一统计口径 |
| 学生账号 | 班级+姓名 定位 | 解决重名问题，支持自助注册 |
| 积分联动 | 表现创建时自动生成积分 | 减少重复录入，积分可追溯 |
| 文件管理 | 试卷上传独立接口 | 格式校验、分块写入、大小限制 |
| 批量导入 | openpyxl + 逐行校验 | 精确错误定位，导入历史可追溯 |
| 平台级配置存储 | 复用 `settings` 表，`school_id IS NULL` 为全局作用域 | 免建新表与迁移，与校内配置共用一套读写约定 |
| 注册开关默认值 | 配置缺失时视为「开放注册」 | 引入开关不改变既有安装行为，避免升级即停摆 |
| 工作台路由组织 | `routers/workbench/` 子包按资源域拆分 | 单文件 1374 行难维护；拆分后对外路径与行为完全不变 |
| 可观测性 | 自研中间件 + `/metrics`，零第三方依赖 | 单实例部署零成本接入 Prometheus；多副本再换共享计数 |