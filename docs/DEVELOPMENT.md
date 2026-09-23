# TeachHub 开发规范

> 面向贡献者与维护者。目标：统一风格、降低协作成本、保证代码可维护。

## 1. 环境搭建

### 1.1 环境要求

| 工具 | 版本 |
| ---- | ---- |
| Python | ≥ 3.10 |
| Node.js | ≥ 18 |
| npm | ≥ 9 |

### 1.2 后端

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate | Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # 运行测试需额外安装
cp .env.example .env          # 按需修改 SECRET_KEY 等
python -m app.seed            # 初始化假数据（可选）
python run.py                 # 启动，默认 :8080
```

### 1.3 前端

```bash
cd frontend
npm install
npm run dev                   # 启动，默认 :5173，代理 /api → :8080
```

### 1.4 Docker（推荐）

```bash
cd teachhub
docker compose up -d --build  # 构建并启动前后端
docker compose logs -f backend
docker compose down           # 停止
```

### 1.5 测试

```bash
cd backend
python -m pytest tests/ -v
```

> ⚠️ **在带 bulk-delete 守卫的受限环境（如 WorkBuddy 沙箱）里必须指定全新 `--basetemp`**：
> pytest 会在结束阶段清理默认临时目录（`%TEMP%/pytest-of-<user>/pytest-N`），撞上守卫会直接
> `SystemExit(1)`，使整轮测试报出**大片假失败**（尤其是用到 `tmp_path` 的图片用例，表现为
> `PermissionError` / `OSError` 与进程非零退出）。绕开方式：
>
> ```bash
> cd backend && python -m pytest --basetemp=<一个全新的目录> -p no:cacheprovider
> ```
>
> 不要据此判断「测试坏了」—— 换 basetemp 重跑即可证伪。

## 2. 配置管理

- 所有环境相关配置走 `.env`（`backend/.env`，模板见 `.env.example`），**严禁硬编码密钥**。
- `.env` 已加入 `.gitignore`，不得提交。
- 生产环境必须覆盖 `SECRET_KEY`（随机 32+ 字节）。

| 变量 | 说明 | 默认 |
| ---- | ---- | ---- |
| `DATABASE_URL` | 数据库连接串 | `mysql+pymysql://root:password@127.0.0.1:3306/teachhub`（开发可切 `sqlite:///./teachhub.db`） |
| `SECRET_KEY` | JWT 签名密钥 | 开发默认值（**生产必改**） |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token 有效期 | `1440`（24 小时） |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 刷新令牌有效期（天） | `30` |
| `MAX_UPLOAD_SIZE` | 上传文件大小上限 | `20971520`（20MB） |
| `AI_MAX_IMAGE_BYTES` | 单张图片送入多模态的字节上限（base64 后约 ×1.37，需明显小于 `MAX_UPLOAD_SIZE`） | `4194304`（4MB） |
| `AI_MAX_IMAGES` | 单次 AI 批改最多送入模型的图片张数（附件 + 正文内嵌**全局合计**） | `6` |
| `AI_IMAGE_MAX_SIDE` | 图片送多模态前的长边上限（仅缩小、绝不放大）。官方每图 token 上限 1024，超过该尺寸只是白增请求体 | `1600` |
| `AI_IMAGE_JPEG_QUALITY` | 图片转 JPEG 时的编码质量（含透明通道的图保留为 PNG，不受此项影响） | `85` |
| `AI_IMAGE_MAX_TOTAL_BYTES` | 单次批改所有图片的合计字节上限（官方请求体上限 48MiB，base64 后约 ×1.37） | `25165824`（24MB） |
| `AI_IMAGE_DETAIL` | 透传 `image_url.detail`：`original` 保留原图 / `low` 缩到 512×512 省 token；留空则不带该字段 | `original` |
| `AI_DEFAULT_MAX_TOKENS` | 单次调用 `max_tokens` 的缺省值（平台设置可覆盖）。**推理模型的思考 token 与正文共用这份预算**，故必须给正文留足余量 | `2048` |
| `AI_THINKING_MODE` | 下发 `thinking.type`：`disabled` 关闭思考（批改属有界抽取任务、不需要长思考，且思考会挤占正文预算）；留空 = 不下发该字段 | `disabled` |
| `AI_REASONING_EFFORT` | 下发 `reasoning_effort`（`low` / `high` / `max`）；留空 = 不下发 | `""` |
| `AI_MAX_TOKENS_CEILING` | 输出被截断时**重试**所允许的 `max_tokens` 上限（防止重试把成本放大到不可控） | `8192` |

> 🔴 **上表中 AI 限额项的「配置默认值」只在 `settings` 表里没有对应行时才生效**。
> `platform_settings.get_ai_*()` 的取值是
> `_as_positive_int(get_global_setting(db, KEY), settings.AI_DEFAULT_*)` ——
> **DB 行优先**。故改 `config.py` 的 `AI_DEFAULT_MAX_TOKENS` **不会**影响已有部署：
> 线上/本地 `settings` 表已存 `ai_max_tokens=1200`，真正的旋钮是**平台设置后台的 `max_tokens`**。
> 排查「改了配置没效果」时先查 `select * from settings where school_id is null;`。

## 3. 后端代码规范

### 3.1 结构约定

- 模型按**业务域**拆分到 `models/` 下独立文件，统一在 `models/__init__.py` 导出。
- 路由按**业务域**拆分到 `routers/`，一个域一个文件；单文件过大时**升级为同名子包**（按资源域拆子模块，`__init__.py` 聚合导出统一 `router`，对外路径与行为保持不变）——现有实例：`routers/workbench/`（`scores` / `leaves` / `communications` / `resources` / `exams` / `seats` / `imports` / `profile` / `reports` + `_common.py`）。
- 新增路由文件（或子包）后需在 `main.py` 中 `include_router`。
- 平台级全局配置读写统一走 `app/platform_settings.py`（`get_global_setting` / `set_global_setting` / `is_registration_allowed`），**不要**在 router 里直接查 `Setting` 表拼 `school_id IS NULL`。
- **分层约定（Service Layer）**：业务逻辑与数据访问放 `app/services/`（子域多时按目录组织，实例 `services/workbench/`）；router 只保留装饰器 / 依赖注入 / 参数解析 / 调用 service / 返回。service 函数统一以 `db: Session` 作为第一参数，可抛 `HTTPException` 以逐字保持状态码与中文文案一致；service **不得 import router**（避免循环依赖）。新增 / 改造接口应**同时**改 service + 薄 router，**不要**把业务逻辑写回 router。
- **分页**：列表接口统一用 `app/pagination.py` 的 `paginate(db, stmt, page, page_size)`（传入未加 `offset/limit` 的 `select()`）；不要再写 `q.count()` + 分页的两次查询。

### 3.2 请求/响应

- 认证相关接口使用 `schemas.py` 中的 Pydantic 模型做校验。
- 新增/改造的写接口**必须**使用 `schemas.py` 中的 Pydantic 模型，不再新增裸 `payload: dict`。已完成迁移的典型：`CommunicationCreate` / `ResourceCreate` / `ExamUpdate` / `SeatSave` / `ReportSave` / `StudentTagCreate` / `RegistrationSetting`；存量 `payload: dict` 接口按需逐步迁移。
- 错误统一抛 `HTTPException(status_code, detail)`，`detail` 使用中文、面向用户。
- **功能开关类接口**：需要在服务端最早的位置拦截（早于参数校验），保证关闭态下任何入参都返回统一的 403 语义，例如 `POST /api/auth/register` 的注册开关守卫。
- **`response_model` 与日期字段**：带 `response_model` 的写接口，若模型字段声明为 `str` 而值是 `datetime/date`，**需先转 ISO 字符串**再返回（Pydantic v2 不做隐式强转，否则抛 `ResponseValidationError`）；参考 `services/workbench/_common.py::stringify_dates`。

### 3.3 权限

- 只读接口用 `Depends(get_current_user)`；写接口按角色挂 `Depends(require_teacher)` / `require_school_admin` / `require_super_admin`，学生端写接口挂 `require_student`。
- **读权限不得比写权限宽**：同一资源的读接口至少要挂与写接口同级的角色依赖。反例（已修）：`routers/workbench/imports.py` 的导入历史读接口一度只挂 `get_current_user`，导致学生能读到含学号的失败明细；现统一为 `dep`（`require_teacher`）。新增「读」接口时对照同资源的「写」接口复核一遍依赖。
- **平台级配置与凭证不复用 `/api/settings`**：全局配置走 `app/platform_settings.py` + `/api/admin/platform/*`（`require_super_admin`）；敏感凭证（如 AI 的 `api_key`）**单独建表、不进 `settings`**（避免明文返回 / 255 容量 / `NULL` 唯一失效三个坑），密钥用 Fernet 加密入库、读接口只回掩码。
- **持久化只存在于数据库的敏感值，读接口一律不回显明文**：如 AI 凭证的 `api_key`，保存响应与读接口都只返回掩码（`mask_secret`），审计只记「改了哪些字段」不记值。
- 任何新增管理端接口**必须**挂 `require_teacher`（教师及以上）；平台级能力（学校开通/启停、跨校概览）挂 `require_super_admin`。
- **多租户隔离（必须）**：所有涉及租户数据的查询/写入必须带 `school_id`。ORM 层已通过 `app/tenant.py` 全局自动隔离（`do_orm_execute` 注入 `school_id` 过滤 + `before_flush` 回填），平台超管（`school_id=NULL`）不受限；跨校按 ID 访问应返回 404（不泄露存在性）。角色判断用 `permissions.is_any_admin()`（本校全量）/ `is_platform_admin()`（跨校），**不要**直接比较 `user.role == "admin"`。
- **写入租户表时 `school_id` 由「业务归属」决定，不能只靠 ORM 自动填充**：`before_flush` 仅在租户上下文有 `school_id` 时回填，而**平台超管的上下文 `school_id` 为 NULL** —— 其写入的租户行会落成 `school_id = NULL`，而租户过滤条件是 `school_id = 当前学校`，NULL 匹配不上，于是该行**对所有学校都不可见**。反例（已修）：平台超管「选为优秀」把 `excellent_works.school_id` 写成 NULL，学生端完全看不到这条优秀作品。规则：父资源明确时（提交→作业、评语→提交、互评→作品）**显式**写 `school_id=<父资源>.school_id`。
- **唯一约束与租户过滤必须同口径**：`excellent_works.submission_id` 这类唯一索引是**全局**的（不随 `school_id` 变化），而应用层「先查后插」的预检走租户过滤 —— 当目标行 `school_id` 为 NULL 或属其他租户时，预检查不到、插入却撞唯一键，用户只能拿到 409「数据冲突：已存在重复记录」且无法自救。规则：**唯一性预检加 `.execution_options(skip_tenant_filter=True)`**，与索引同口径、返回可理解的 400；同时**预检前必须先完成租户可见性与归属校验**（`db.get()` 带过滤天然 404），否则放宽口径会引入越权。参考 `homework_service._find_excellent_of_submission`。
- **按全局唯一键定位的行，读路径同样要跳过租户过滤**：`submission_id` 这类全局唯一键决定行身份，一行只可能属于一个提交；若查询被注入 `school_id = 当前租户`，一旦该行归属异常（`NULL` 或他校）就会「读不到自己的行」—— 轻则教师看到「未批改」，重则 `INSERT` 撞唯一索引报 **1062**（线上事故，见 `CHANGELOG.md` 续 24）。同理，**写入租户行时必须显式 `school_id=<父资源>.school_id`，不能只靠 ORM 自动回填** —— 平台超管的上下文 `school_id` 为 NULL 时回填是空操作。注意：ORM **批量** `delete()` / `update()` 本就不经租户过滤（`tenant.py` 只对 SELECT 注入），只有单行 SELECT 定位才需要显式 `skip_tenant_filter`。
- 教师班级数据隔离**统一**走 `permissions.get_teacher_class_ids()` / `is_teacher_class_owner()`，这两个函数已支持「班主任 + 科任老师」多教师模型；**不得**直接比较 `Classroom.teacher_id` 做权限判断，否则会漏掉科任老师。
- **登录/注册限流**：认证入口用 `slowapi` 的 `@limiter.limit("5/minute")`（登录）/ `("10/minute")`（注册）装饰；`main.py` 已挂 `app.state.limiter` 与 `RateLimitExceeded` handler，新增认证端点须沿用该模式。

### 3.4 模型变更

- 新增字段/表：修改模型定义后，必须配套新增 Alembic migration（`backend/alembic/versions/`）
- 生成迁移脚本：`cd backend && alembic revision --autogenerate -m "描述"`，人工核对后提交
- 应用到本地库：`alembic upgrade head`（本地启动或 Docker 启动会自动执行）
- 确保「迁移链」与「模型 schema」保持一致，避免依赖 `create_all` 兜底而遗漏加列
- **多租户约束调整**：改唯一约束（如 `settings.key` 全局唯一 → `(school_id, key)` 校内唯一）时，SQLite 不支持 `DROP CONSTRAINT`，需在迁移中**重建表**（新建→拷贝→删除→重命名），参考 `f1a2b3c4d5e6_settings_school_key_unique.py`；MySQL/PostgreSQL 可直接 `drop_constraint` + `create_unique_constraint`。
- **手动改库须同步 `alembic_version`**：`main.py` 启动自动 `upgrade head`，若先用 SQL 手动改了库再触发迁移会重复执行报错（如 DROP INDEX 1091）。手动改库后需 `UPDATE alembic_version SET version_num='<rev>'` 到对应 revision。
- **外键删除规则分层**：纯从属关系用 `ondelete="CASCADE"`（作业链、学生业务链，共 18 个，含 `ai_grading_results`→`submissions`）；归属/操作人关系保持 RESTRICT（`teacher_id`/`created_by`/`school_id`/`class_id` 等，共 54 个）；另有 1 个 SET NULL（`refresh_tokens.school_id`，租户归属可空）。模型定义口径合计 73 个外键。应用层 `cleanup.py` 的 `purge_student_data`/`purge_user_data` 按「叶子→根」拓扑倒序删除作双保险，与 CASCADE 兼容。
- **🔴 与 `created_at` 比时间必须用数据库时钟**：本项目时间戳统一由 `server_default=func.now()` 生成（SQLite 为 **UTC**、MySQL 为**库本地时区**），而 Python 的 `date.today()` 取的是**进程本地日期**。两者的时区基准不保证一致（例如 SQLite 下本地 03:20 属于 UTC 前一天），用 `created_at >= 本地今日零点` 会把当天记录整片过滤掉 —— AI 批改的每日限额就曾因此**恒为 0、永不触发**。正确写法是让数据库自己算边界，如 `func.date(Col.created_at) == func.current_date()`（参考 `services/ai_grading.py::today_call_count`）。历史数据 `admin_service.py` 的周统计也有 `date.today()`，改动涉及跨日统计时需一并核对。

### 3.5 工具函数与辅助

- 公共工具统一放 `app/utils.py`：`to_dict` / `safe_filename` / `gen_student_no`（生成学号）/ `normalize_page`（分页边界规范化，所有分页列表接口须调用）。
- 权限/租户辅助统一放 `app/permissions.py`：`is_any_admin` / `is_platform_admin` / `get_teacher_class_ids` / `get_student_account`（按班级+姓名查学生账号）/ `ensure_student_access` 等，**不得**在各 router 重复实现。
- 分页参数必须调用 `normalize_page(page, page_size)`（防负数/超大 page_size），删除类接口记录不存在时统一返回 `404`。

### 3.6 文件上传

- 通用上传使用 `POST /api/uploads`，自动校验扩展名白名单和大小上限。
- 业务专用上传（如试卷）使用独立接口，格式校验更严格。
- 上传文件存储在 `backend/uploads/`，通过 `/uploads/<filename>` 访问。
- **图文混排模块的图片**：图片 url 直接内嵌在正文 Markdown（`![图片](url)`）中，不再单独维护图片字段；历史字段（`activities.filepath` / `talks.images`）保留以兼容旧数据，但新写入不再使用。
- **消费正文的模块必须处理内嵌图片**：正文里的 `![图片](url)` 对后端只是一段文本。任何需要「看到」图片的消费方（如 AI 批改）都必须显式解析这些引用并取出图片（参考 `services/ai_attachments.extract_inline_images`），**不能只读 `filepath` 之类的独立附件字段** —— 富文本插入的图片不会写进那些字段（历史缺陷，见 `CHANGELOG.md` 续 21）。
- **只送模型真正支持的图片格式，且按内容判定**：`deepseek-flash` 视觉接口仅接受 **JPEG / PNG / GIF / WebP**，且**格式由文件实际内容判定**（`services/ai_image.sniff_format` 按魔数），**不能按扩展名推 MIME**。BMP / HEIC / TIFF 等一律降级为「未参与批改」，**绝对不能送** —— 一次 400 会让**整份作业**的批改失败（见 `CHANGELOG.md` 续 23）。图片送入前还要经 `services/ai_image.prepare_data_url` 预缩放（官方每图 token 上限 1024，超过 `AI_IMAGE_MAX_SIDE` 只是白增请求体）并摆正 EXIF 方向（手机照片横躺会显著拉低手写字识别率）。

### 3.7 审计日志

- 关键写操作调用 `audit(db, user, action, target, detail, class_id=None, student_id=None)` 记录。
- **学生相关操作必须传 `student_id`**（函数自动解析班级），**班级相关操作必须传 `class_id`**，用于班主任按班级查看审计日志；账号/系统级操作无需传。
- 审计日志存储在 `operation_logs` 表。
- 查看权限分级：管理员全部、班主任自己班级、科任老师不可见（由 `admin._visible_audit_class_ids` 控制）。
- 新增的写操作要同步在 `admin.py` 的审计操作类型映射与前端 `AuditLogs.vue` 的中文标签映射中登记，避免日志页显示原始 action 串。

### 3.8 可观测性

- **访问日志**：`app/observability.py` 的中间件为每个请求记录 `方法 + 路径 + 状态码 + 耗时`，耗时 ≥ 1s 标 `[SLOW]`。
- **请求链路 ID（`X-Request-ID`）**：中间件读入站 `X-Request-ID` 请求头（缺失则生成 `uuid4`）并写回响应头；日志行统一带 `[rid=...]`，用于跨日志串联同一请求。实现见 `app/logging_config.py`（`ctx_request_id` / `get_request_id` / `set_request_id` / `reset_request_id` / `new_request_id`）。
- **结构化日志**：`app/logging_config.py` 的 `RequestIdFilter` 把当前 request-id 注入日志记录，`StructuredFormatter` 统一输出格式，`setup_logging()` 取代 `logging.basicConfig` 统一初始化 handler。
- **日志落盘**：`main.py` 的 `_setup_file_logging()` 将访问日志与业务日志写入 `backend/logs/teachhub.log`（`TimedRotatingFileHandler` 按天滚动、保留 30 天）。
  - ⚠️ 该函数**必须在 `run_migrations()` 之后调用**（Alembic 会重置 root logger 的 handler）。
  - ⚠️ uvicorn 启动时 `dictConfig(disable_existing_loggers=True)` 会禁用已有 logger，需对 `teachhub.access` 显式 `disabled=False` + `propagate=False` + 直接 `addHandler(file_handler)`。
- **指标**：`/metrics` 输出 Prometheus 文本格式（请求计数、状态码分布、耗时直方图、慢请求数、进行中请求数），零第三方依赖；多副本部署时需改为共享计数。
- 新增中间件务必保持「最外层」位置，避免被异常处理或鉴权拦截影响日志完整性。

### 3.9 外部模型调用（推理模型的坑）

- **🔴 推理模型的「思考 token」与正文**共用**同一份 `max_tokens` 预算**：DeepSeek 的
  `deepseek-flash`（V4.1-Flash）等推理模型，**思考模式默认打开且 `reasoning_effort` 默认
  `high`**；思考内容经 `reasoning_content` 返回、与 `content` 同级，但**两者从同一份
  `max_tokens` 里扣**。预算偏小时会得到「`finish_reason == "length"` **且 `content` 为空**」——
  看起来像模型不干活，实际是预算全被思考吃掉（线上事故：`max_tokens=1200` → 批量批改 100% 失败）。
  规则：**有界抽取类任务（批改、分类、结构化输出）必须显式关闭思考**
  （`{"thinking": {"type": "disabled"}}`），**不要**指望靠调大 `max_tokens` 解决 ——
  社区实测 effort=high 下给到 8000 仍可能被吃光。
- **服务商专有字段必须门控**：`thinking` / `reasoning_effort` 是 DeepSeek **专有** body 字段，
  其他 OpenAI 兼容服务商对未知字段可能直接 **400**。参考
  `services/ai_client.py::supports_thinking_control`（仅 `base_url` 含 `deepseek` 时下发）。
- **截断要能自愈**：`services/ai_grading.py::_call_model` 在首次调用被截断时，用
  `min(max_tokens × 3, AI_MAX_TOKENS_CEILING)` **重试一次**；仍截断才如实记 `failed`
  （配合 §「输出不完整不得假装成功」的诚实性守卫）。
- **诊断必须看 `reasoning_tokens`**：`chat_completion` 回传 `finish_reason` 与
  `reasoning_tokens`；排查「正文为空」时先看这两个值，不要只看 `content`。
- **账号级错误要「给人话」且不重试**：`401/402/403`（密钥无效 / **余额不足** / 无模型权限）
  与 `429` 属于「先去平台处理账号，再谈重试」，重试不会有不同结果 —— 故**不进入截断重试路径**。
  同时 `error` 字段面向教师展示，必须归一化为「**中文结论**（服务返回 N：原始片段）」，
  实现在 `ai_client._HTTP_ERROR_HINTS` / `_describe_http_error()`；
  未映射的状态码保持原格式，**不臆造结论**。线上实例：`402 Insufficient Balance`
  （DeepSeek 余额耗尽）此前会原样把英文 JSON 抛给教师，无从下手。
- **重复内容「靠缓存便宜」，不靠「少发」**：批改是无状态调用，任务附件**必然**随每份提交
  重复送入（40 人班 = 40 次）。对策是让重复的那段**便宜**：稳定内容（`system` + 作业要求 +
  任务附件）放消息**最前**、逐份变化的提交内容放最后 —— DeepSeek 会自动对这段前缀做硬盘缓存
  （**无需任何开关**），命中部分按 1/10~1/50 计价。**排错要点**：改配置文件顺序会破坏前缀缓存；
  更重要的是**别走中转 / 聚合平台**（实测返回 `cached_tokens: 0`，折扣全丢），
  用日志里的「缓存命中」字段核对（`None` = 端点不回传 = 正按原价重复计费）。
- **本地抽取要按批复用**：`ai_attachments.extract_attachment(filepath, filename, cache=True)`
  按 `(路径, mtime_ns, size, vision_enabled, 配置指纹)` 缓存；**任务附件开、学生提交附件不开**
  （后者每份都不同，开缓存零收益还占内存）。缓存键含 `mtime_ns`，所以覆盖同名文件会自动失效；
  含配置指纹，所以改 `AI_MAX_ATTACHMENT_CHARS` 立即生效。测试里可用
  `ai_attachments.clear_attachment_cache()` 复位。
- ⚠️ 思考模式下 `temperature` / `presence_penalty` / `frequency_penalty` **不生效**
  （设置不报错，但也不会生效）。
- ⚠️ 连通性自检（`ai_client.test_connection`）也必须下发同样的思考设置，否则对推理模型会
  **误报连接失败**（旧实现用 `max_tokens=8`，思考一开必然吃空正文）。

## 4. 前端代码规范

### 4.1 结构约定

- 页面放 `views/`，按 `student/`、`admin/` 分组；跨页复用的组件放 `components/`。
- **巨型页面组件拆分**：单文件过大时拆为「编排层 + 页内子组件」，编排层（同名 `.vue`）只保留列表/分页/取数与弹窗编排，子组件下沉**同名子目录**（`views/admin/students/`、`views/admin/scores/`）；仅在**本页复用**的子组件放该子目录，**不**提升到全局 `components/`。拆分须**行为等价**（接口调用、文案、字段、列宽、按钮顺序、刷新时机不变），并优先消除跨页重复实现（抽公共件）。
- **布局外壳不得下沉**：`layout/AdminLayout.vue` / `StudentLayout.vue` 的 `el-container` / `el-aside` / `el-header` 等**直接子节点容器**必须留在布局文件内——Element Plus `el-container` 靠「直接子节点的组件名」推断 flex 方向，容器下沉会破坏布局。带 scoped 样式的子组件（如 `.brand-text` 的 `.fade-*` 过渡）须连同样式一起迁移，否则父级 scoped 规则命中不到。
- **移动端页面放 `mobile/views/`**，布局放 `mobile/layout/`，使用 Vant 组件（`van-*`），与桌面端 Element Plus（`el-*`）互不干扰。
- API 调用统一收敛到 `api/index.js`（移动端专用接口放 `mobile/api/mobile.js`），页面**不得**直接 import axios。
- 路由统一在 `router/index.js` 注册，角色守卫统一走 `beforeEach`；移动端路由前缀 `/m`，同样纳入 `requiresTeacher` 校验。
- **状态管理用 Pinia**：全局状态放 `stores/`（如 `auth.js`），组件内 `useAuthStore()` 取响应式状态；不要直接反复解析 localStorage。`utils/auth.js` 的 `setAuth`/`clearAuth` 通过 `getActivePinia()` + 动态 import 惰性同步 store，避免循环依赖。

### 4.2 组件风格

- 统一使用 `<script setup>` + Composition API。
- 使用全局 CSS 变量（`--brand`、`--text-*`、`--bg-*` 等）而非硬编码颜色。
- Element Plus 图标通过 `main.js` 全局注册，页面直接 `<el-icon><Xxx /></el-icon>`。
- 表单校验：必填字段在提交前显式校验并 `ElMessage` 提示；复杂校验建议上 `el-form` rules。
- **防重复提交**：写操作在组件内用本地 `saving` ref 实现（`:loading="saving"` 绑到提交按钮，Element Plus 在 loading 期间不可点），**没有**统一 composable；网络层 `request.js` 另做并发去重（同「方法+URL+参数」取消前一个，AbortController + pending Map），两道合起来兜住快速与慢速重复点击。
- **文件下载**：Excel 等文件导出复用 `src/composables/useDownload.js` 的 `downloadExcel(data, filename)`（内部封装 `Blob → createObjectURL → click → revoke`），不要在页面里重复写这套样板。
- **通用弹窗**：Excel 批量导入复用 `src/components/ImportDialog.vue`（`v-model` 控制显隐，`importFn` / `templateUrl` / `importType` 注入业务差异，`@success` 回调刷新列表）；弹窗内自带「最近导入记录」（按 `importType` 拉 `GET /api/import-history`，展开可见逐行失败原因），不要在页面里重复实现导入弹窗。
- **统一体验态（强制约定）**：列表页的「加载 / 空 / 错误」一律用 `src/components/StateView.vue` 接入，**不要再手写 `v-if` 判断或直接用 `el-empty`**。把 `<el-table>`（或自绘列表）包进去，传 `:loading` / `:error` / `:empty` 与 `@retry="load"`：
  ```vue
  <StateView
    :loading="loading" :error="error" :empty="!items.length"
    :columns="6" empty-description="暂无记录" @retry="load"
  >
    <template #empty><el-button type="primary" @click="openCreate">新建</el-button></template>
    <el-table :data="items" v-loading="loading">...</el-table>
  </StateView>
  ```
  配套的 `load()` 固定写法（顺序不可颠倒，否则错误态判定会失效）：
  ```js
  async function load() {
    loading.value = true
    error.value = false        // 必须在 try 之前
    try { /* ... */ } catch (e) {
      error.value = true       // 不要在这里再加 ElMessage.error，全局拦截器已弹
    } finally { loading.value = false }
  }
  ```
  **保留 `el-table` 上的 `v-loading`**：骨架屏只在首屏出现，后续刷新靠它反馈。非表格页面（图表 / 画像）可用 `#skeleton` 具名插槽自定义骨架。
- **AI 批改展示**：**学生端**的 AI 批改意见统一复用 `src/components/AiGradingPanel.vue`（`:ai` 传 `ai_grading` 对象；纯展示、学生口径，不含 `error` / `model` / `excellent_reason`）。**教师端刻意不复用** —— 教师侧 AI 区块带「采纳为优秀 / 重新批改」等交互与教师专属字段，保留各自实现。新增学生端 AI 展示位请复用它，**不要**再内联复制这套模板与样式。
- **虚拟滚动**：固定行高的长列表用 `src/components/VirtualList.vue`（`:items` + `:item-height` + `:height`，默认插槽作用域为 `{ item, index }`），避免一次性渲染海量行。注意它自任滚动容器，**不要嵌在 `van-pull-refresh` 之类自身依赖滚动位置的容器内**。

### 4.3 样式系统

- 全局样式在 `style.css` 中定义，包含 CSS 变量、组件覆盖、Markdown 渲染样式。
- 页面级样式使用 `<style scoped>`，避免污染全局。
- 通用类名：`.page-card`（卡片容器）、`.toolbar`（工具栏）、`.card-title`（卡片标题）、`.empty-state`（空状态）。

### 4.4 安全

- Markdown 渲染**必须**经过 `DOMPurify.sanitize()` 进行 XSS 过滤。
- 文件上传/下载使用 Blob 方式处理，注意 `responseType: 'blob'`。
- Token 存储在 localStorage（`teachhub_token` + `refresh_token`），请求时通过 Axios 拦截器自动注入。
- **令牌刷新（约定）**：`request.js` 对**非登录接口**返回的 `401` 做**单飞静默刷新**（并发请求共享同一次刷新，避免刷新风暴），成功后用新 token 重放原请求一次，仅当刷新失败才跳转登录页。新增接口**无需**自行处理令牌刷新，也不要自己再次跳登录。
- **登出（约定）**：登出 / 切换身份一律用 `src/composables/useLogout.js` 的 `useLogout()`（`const logout = useLogout(); logout('/admin/login')`），它会先撤销服务端刷新令牌、再清理本地登录态并跳登录页。**不要**再直接调 `clearAuth()`——access token 是无状态 JWT 不可撤销，只清本地会让服务端刷新令牌（默认 30 天）继续可用。

### 4.5 代码规范工具

- ESLint 10（flat config，`eslint.config.js`）+ Prettier 3（`.prettierrc.json`）。
- 脚本：`npm run lint`（检查）、`npm run lint:fix`（修复）、`npm run format`（格式化）。
- 提交前确保 `npm run lint` 0 error（warning 可接受）。
- **工程规范（仓库根）**：提交信息遵循 Conventional Commits，校验由 commitlint + lint-staged 承担 —— 规则文件在仓库内（`commitlint.config.cjs`：type 限 `feat/fix/refactor/docs/chore/test/perf/build/ci`，scope 限 `backend/frontend/docs/deps`；`.lintstagedrc.json`：`frontend/src/**/*.{js,vue}` 跑 `eslint --fix` + `prettier --write`）。⚠️ **`.husky/` 钩子目录当前未纳入版本控制**（`git config core.hooksPath` 指向 `.husky/_`，但该目录不存在）—— 需在**仓库根**执行一次 `npm install` 生成后才生效，未生成前提交不会触发校验；后端测试用 `pytest`（`backend/pytest.ini` 已限定 `testpaths = tests`）。

## 5. Git 规范

### 5.1 分支模型（简化 Git Flow）

```
main          # 稳定，可发布
  └── develop # 集成
        └── feature/xxx   # 功能分支
        └── fix/xxx       # 修复分支
```

### 5.2 Commit Message 规范（Conventional Commits）

```
<type>(<scope>): <subject>

type: feat | fix | docs | refactor | test | chore | perf | style
```

示例：
```
feat(homework): 支持教师批量评选优秀作品
fix(auth): 修复 token 过期后未跳转登录页
docs: 补充架构设计文档
```

### 5.3 提交前自检

- [ ] 代码可无报错运行（后端 `pytest`，前端 `npm run build`）
- [ ] 无硬编码密钥、密码
- [ ] 涉及数据库的改动已新增 Alembic 迁移（`backend/alembic/versions/`）
- [ ] 新增接口已挂权限依赖
- [ ] 新增前端页面已在路由中注册

## 6. 测试规范

- 后端：pytest + TestClient，覆盖**登录、权限隔离、核心 CRUD、越权场景**。
- 新增接口必须补对应测试（至少一条正常 + 一条越权/异常）。
- 前端：建议补充 Vitest 组件测试。
- 目标：核心链路覆盖率 ≥ 70%。

## 7. 发布流程（Checklist）

1. `cd backend && python -m pytest tests/ -v` 全绿
2. `cd frontend && npm run build` 构建成功
3. 生产 `.env` 覆盖 `SECRET_KEY`、`DATABASE_URL`，并设置 `ENV=production`
4. 数据库迁移：`cd backend && alembic upgrade head`
5. Docker 部署：`docker compose up -d --build`，验证 `/health` 与登录链路
6. 打 tag：`git tag v1.0.0 && git push --tags`

## 8. 文档维护

| 变更类型 | 需要更新的文档 |
| ---- | ---- |
| 架构/目录/依赖变更 | `docs/ARCHITECTURE.md` |
| 新增/修改接口 | `docs/API.md` |
| 模型/表结构变更 | `docs/ER-DIAGRAM.md`（并配套 Alembic 迁移） |
| 开发规范变更 | `docs/DEVELOPMENT.md` |
| 功能与快速开始 | `README.md` |
| 每次功能/修复/重构 | `docs/CHANGELOG.md`（按时间倒序追加） |
| 迭代需求 / 产品规划 | `docs/REQUIREMENTS.md`（移动端）、`docs/MULTI-TENANT-PRD.md`（多租户） |
| AI 批改需求与边界 | `docs/AI-GRADING-PRD.md`（需求分级、可见性口径、成本护栏、决策记录与待决项） |
| 技术方案 | `docs/MOBILE-TECH.md`、`docs/MULTI-TENANT-TECH.md`、`docs/system_design.md` |

> 约定：**接口与模型类文档（API / ER-DIAGRAM）必须与代码同步更新**，否则以代码为准并视为文档缺陷。可用以下命令从代码导出「地面事实」用于校对：
>
> ```bash
> cd backend && python -c "from app.main import app; print(len(app.routes))"        # 路由数
> cd backend && python -m pytest tests/ -v                                          # 测试
> ```