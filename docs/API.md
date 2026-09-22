# TeachHub API 接口文档

> 更新：2026-09-22 ｜ 前缀约定：所有接口以 `/api` 开头；作业平台以 `/api/homework` 为前缀；认证以 `/api/auth` 为前缀
>
> 认证方式：请求头 `Authorization: Bearer <token>`（登录/注册/注册开关状态/学校下拉/班级下拉/刷新令牌/登出/编程练习无需认证）。
> 令牌双轨：登录返回的访问令牌字段名为 `token`（短期有效，用于鉴权），另有 `refresh_token`（长期有效，用于换取新令牌对，详见「一、认证」末段）。
>
> 链路追踪：所有响应均带 `X-Request-ID` 响应头（请求头传入则透传，否则服务端生成 `uuid4`）；服务端日志每行带 `[rid=...]`，可用该 ID 串联同一请求的全部日志。
>
> 规模：**业务接口 145 条**（`/api/**`）+ 8 条非业务路由（端点 `/`、`/health`、`/metrics`、`/docs`、`/docs/oauth2-redirect`、`/redoc`、`/openapi.json` + `/uploads` 静态挂载），合计 153 条已注册路由（以 `len(app.routes)` 为准）

## 角色权限说明

| 角色 | 标识 | 权限范围 |
| --- | --- | --- |
| 学生 | `student` | 仅作业提交平台 |
| 教师 | `teacher` | 本校自己负责班级（班主任 + 科任） |
| 学校管理员 | `school_admin` | 本校全部 |
| 平台超管 | `super_admin` | 跨校全部 |

## 一、认证 `/api/auth`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 公开 | 登录（限流 5 次/分钟，锁定 5 次/15 分钟）；返回 `{token, refresh_token, user, must_change_password}` |
| POST | `/api/auth/refresh` | 公开 | 用 `refresh_token` 换取新令牌对，返回 `{token, refresh_token, token_type}`（限流 30 次/分钟；失败返回 401） |
| POST | `/api/auth/logout` | 公开 | 撤销刷新令牌，返回 `{ok: true}`（幂等：重复调用仍返回成功；凭令牌本身即可调用，无需鉴权） |
| POST | `/api/auth/register` | 公开 | 学生自助注册（限流 10 次/分钟；平台关闭注册时返回 403） |
| GET | `/api/auth/schools` | 公开 | 启用中学校下拉 |
| GET | `/api/auth/registration-status` | 公开 | 学生自助注册开关（返回 `{allow_registration: bool}`） |
| GET | `/api/auth/me` | 登录 | 当前用户信息 |
| PUT | `/api/auth/password` | 登录 | 修改密码（需旧密码）；成功后**吊销本账号全部会话**（自增 `users.token_version` + 撤销未过期 refresh token，旧 access token 立即失效） |
| POST | `/api/auth/avatar` | 登录 | 上传自己头像 |

**刷新令牌（refresh token）机制**

- **请求体**：`POST /api/auth/refresh` 与 `POST /api/auth/logout` 均接收 `{"refresh_token": "<opaque>"}`，返回 JSON。
- **存储**：服务端仅存令牌的 `sha256` 摘要（表 `refresh_tokens`：`user_id` / `school_id` / `token_hash` / `expires_at` / `revoked_at` / `replaced_by`，默认有效期 30 天，可用环境变量 `REFRESH_TOKEN_EXPIRE_DAYS` 调整），明文不落库。访问令牌 `token` 有效期由 `ACCESS_TOKEN_EXPIRE_MINUTES` 控制（默认 1440 分钟）。
- **轮换（rotation）**：每次 `/refresh` 都会签发**新的** `token` + `refresh_token` 令牌对，并立即撤销旧 refresh_token（`replaced_by` 指向新令牌）。旧令牌被重放时返回 401。
- **前端行为**：`src/api/request.js` 在收到 401（非登录接口）时**静默刷新**并重放原请求一次；并发 401 走**单飞（single-flight）**，共享同一个刷新 Promise，仅发起一次 `/refresh`。刷新失败则清理登录态并跳转登录页。
- **登出**：应同时调用 `/api/auth/logout` 撤销服务端令牌并清理本地存储；`logout` 为幂等操作。

## 二、公共 `/api/meta`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/meta/classes` | 公开 | 班级下拉（可选 school_id，仅未毕业） |
| GET | `/api/meta/practice` | 公开 | 编程练习推荐 |

## 三、作业平台 `/api/homework`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/assignments` | 登录 | 作业列表（学生看本班，教师看自己班级） |
| GET | `/assignments/{id}` | 登录 | 作业详情 |
| POST | `/assignments` | 教师+ | 布置作业 |
| PUT | `/assignments/{id}` | 教师+ | 编辑作业 |
| DELETE | `/assignments/{id}` | 教师+ | 删除作业 |
| GET | `/assignments/{id}/submissions` | 登录 | 提交列表（教师侧附 `ai_grading_status` / `ai_score` / `ai_excellent_candidate`，用于「AI 批改」按钮的结果反馈） |
| GET | `/assignments/{id}/unsubmitted` | 教师+ | 未交名单（应交 = 班级在籍学生，未交 = 应交 − 已交） |
| POST | `/assignments/{id}/ai-grade` | 教师+ | **触发 AI 批改（教师手动，批量）**：批改该作业下**尚未成功批改**的提交；已批改的跳过，剩余额度不足时按额度截断。返回 `{queued, skipped, already_graded, reason}`。非阻塞（仅入队）。开关关 / 无凭证 / 额度耗尽 → 400 |
| POST | `/assignments/{id}/submissions` | 学生 | 提交作业（**不触发任何 AI 调用**） |
| GET | `/submissions/{id}` | 登录 | 提交详情（含 `assignment_title` + 点评 + 评优信息 excellent_id/excellent_note + AI 批改 `ai_grading`）。AI 结果**仅本人可见**（学生读他人提交 403）；学生侧**不含** `error`（失败原因只给教师） |
| POST | `/submissions/{id}/ai-grade` | 教师+ | **触发 AI 批改（教师手动，单份）**：已有结果则重跑覆盖（用于补批失败件或重交后重批）。返回 `{queued, skipped, reason}`。开关关 / 无凭证 / 额度耗尽 → 400 |
| POST | `/submissions/{id}/comments` | 教师+ | 添加点评（含评分 0-100） |
| DELETE | `/submissions/{sid}/comments/{cid}` | 教师+ | 删除点评 |
| GET | `/my-submissions` | 学生 | 我的提交（附 `ai_grading_status`：`success` / `pending` / `failed` / `null`） |
| POST | `/submissions/{id}/excellent` | 教师+ | 评优秀（`from_ai=true` 时 `excellent_works.source` 记 `ai_recommended`，用于「AI 推荐采纳」来源追溯）。`school_id` 取**提交所属学校**（不取操作者）；重复评选返回 **400**「该作品已入选优秀」 |
| DELETE | `/submissions/{id}/excellent` | 教师+ | 取消优秀（幂等；提交不存在返回 **404**，跨校 404） |
| GET | `/excellent` | 登录 | 优秀作品列表（学生看**本班**，教师看自己班级，平台超管全量） |
| GET | `/excellent/{id}` | 登录 | 优秀作品详情（含 `note` 评选评语 + `teacher_comments` 批改评语列表 + AI 批改 `ai_grading`）。`ai_grading` 与 `/submissions/{id}` 同口径（学生侧**不含** `error`）。⚠️ 可见范围为 **`school_id` 同校**（含同校学生），与 `/submissions/{id}` 的「仅本人」不同——优秀作品本就公开，AI 意见与 `teacher_comments` 随作品一并可见（**该可见性经 `AI-GRADING-PRD.md` §8.1 Q10 拍板接受，2026-09-22**） |
| POST | `/excellent/{id}/comments` | 登录 | 发表评论 |

## 四、基础数据

### 学校（平台超管）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/schools` | 登录 | 学校列表 |
| POST | `/api/schools` | 超管 | 创建学校 |
| PUT | `/api/schools/{id}` | 超管 | 修改学校 |
| DELETE | `/api/schools/{id}` | 超管 | 删除学校 |
| PUT | `/api/schools/{id}/status` | 超管 | 启停学校 |

### 班级

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/classrooms` | 教师+ | 班级列表（graduated 筛选） |
| POST | `/api/classrooms` | 管理员 | 创建班级 |
| PUT | `/api/classrooms/{id}` | 登录 | 修改班级 |
| DELETE | `/api/classrooms/{id}` | 管理员 | 删除班级 |
| GET | `/api/classrooms/{id}/teachers` | 登录 | 班级教师列表 |
| POST | `/api/classrooms/{id}/teachers` | 管理员 | 添加科任 |
| DELETE | `/api/classrooms/{id}/teachers/{tid}` | 管理员 | 移除科任 |

### 学生

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/students` | 教师+ | 学生列表（keyword/class_id/dropped_out 筛选） |
| POST | `/api/students` | 教师+ | 创建学生（自动建账号） |
| PUT | `/api/students/{id}` | 登录 | 修改学生 |
| DELETE | `/api/students/{id}` | 登录 | 删除学生（级联清理） |
| PUT | `/api/students/{id}/password` | 登录 | 重置学生密码；成功后**吊销该学生全部会话**（同 `/api/auth/password` 的 `token_version` 机制） |
| POST | `/api/students/{id}/avatar` | 登录 | 上传学生头像 |
| GET | `/api/students/{id}/profile` | 登录 | 学生画像（四维雷达） |
| POST | `/api/students/{id}/tags` | 登录 | 添加标签 |
| DELETE | `/api/students/{id}/tags/{tag_id}` | 登录 | 删除标签 |
| GET | `/api/students/{id}/board-history` | 登录 | 住宿变更历史 |
| GET | `/api/students/board-type-stats` | 登录 | 通学/寄宿统计 |
| GET | `/api/students/export` | 登录 | 导出花名册 |
| GET | `/api/students/template` | 教师+ | 导入模板 |
| POST | `/api/students/import` | 教师+ | 批量导入 |

## 五、教师工作台

### 成绩

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/scores` | 登录 | 成绩列表 |
| GET | `/api/scores/analysis` | 登录 | 成绩分析（班级排名 + 趋势）；**排名口径**：未显式指定 `exam_name` 时，默认收敛到所选科目的**最近一次考试**内排名（不再跨科、跨场混合），响应回传 `ranking_basis = {subject, exam}` 供前端展示口径 |
| POST | `/api/scores` | 登录 | 录入成绩 |
| PUT | `/api/scores/{id}` | 登录 | 修改成绩 |
| DELETE | `/api/scores/{id}` | 登录 | 删除成绩 |
| GET | `/api/scores/export` | 登录 | 导出成绩 |
| GET | `/api/scores/template` | 教师+ | 导入模板 |
| POST | `/api/scores/import` | 教师+ | 批量导入 |

### 请假 / 考勤 / 沟通 / 资源 / 试卷 / 座位

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET/POST | `/api/leaves` | 登录 | 请假列表/登记 |
| PUT/DELETE | `/api/leaves/{id}` | 登录 | 请假修改/删除 |
| GET | `/api/attendance` | 登录 | 考勤查询（class_id + date） |
| POST | `/api/attendance/checkin` | 登录 | 批量点名 |
| GET | `/api/attendance/summary` | 登录 | 出勤率统计 |
| GET/POST | `/api/communications` | 登录 | 沟通列表/新增 |
| DELETE | `/api/communications/{id}` | 登录 | 删除沟通 |
| GET/POST | `/api/resources` | 教师+ | 资源列表/新增 |
| DELETE | `/api/resources/{id}` | 教师+ | 删除资源 |
| GET | `/api/exams` | 教师+ | 试卷列表 |
| POST | `/api/exams/upload` | 登录 | 上传试卷 |
| PUT | `/api/exams/{id}` | 教师+ | 修改试卷 |
| GET | `/api/exams/{id}/download` | 教师+ | 下载试卷 |
| DELETE | `/api/exams/{id}` | 教师+ | 删除试卷 |
| GET | `/api/seats` | 登录 | 座位表查询 |
| PUT | `/api/seats` | 登录 | 保存座位表 |
| GET | `/api/import-history` | 登录 | 导入历史 |

## 六、班级日志

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET/POST | `/api/work-logs` | 登录/教师+ | 工作日志列表/新增 |
| PUT/DELETE | `/api/work-logs/{id}` | 登录 | 日志修改/删除 |
| GET/POST | `/api/class-plans` | 登录/教师+ | 班级计划 |
| PUT/DELETE | `/api/class-plans/{id}` | 登录 | 计划修改/删除 |
| GET/POST | `/api/teacher-plans` | 登录/教师+ | 个人计划 |
| PUT/DELETE | `/api/teacher-plans/{id}` | 登录 | 计划修改/删除 |
| GET/POST | `/api/schedules` | 登录 | 课表 |
| DELETE | `/api/schedules/{id}` | 登录 | 删除课表 |
| GET/POST | `/api/activities` | 登录 | 活动 |
| DELETE | `/api/activities/{id}` | 登录 | 删除活动 |
| GET/POST | `/api/talks` | 登录 | 谈心 |
| DELETE | `/api/talks/{id}` | 登录 | 删除谈心 |
| GET/POST | `/api/return-records` | 登录 | 返校记录 |
| DELETE | `/api/return-records/{id}` | 登录 | 删除返校 |
| GET/POST | `/api/performances` | 登录 | 表现（含积分） |
| GET | `/api/performances/summary` | 登录 | 表现（含积分）汇总：`delta`/`positive`/`negative`/`count`/`student_count`，随列表筛选联动 |
| DELETE | `/api/performances/{id}` | 登录 | 删除表现 |
| GET | `/api/student-comments/suggest` | 登录 | 评语生成草稿 |
| GET/POST | `/api/student-comments` | 登录 | 评语列表/新增 |
| PUT/DELETE | `/api/student-comments/{id}` | 登录 | 评语修改/删除 |

## 七、系统管理 `/api/admin`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/users` | 管理员 | 账号列表 |
| POST | `/users` | 管理员 | 创建账号 |
| PUT | `/users/{id}` | 管理员 | 修改账号 |
| PUT | `/users/{id}/password` | 管理员 | 重置密码；成功后**吊销目标账号全部会话**（`token_version` 自增 + 撤销 refresh token）。权限：`school_admin` 只能重置**本校**账号，`super_admin` 不限 |
| DELETE | `/users/{id}` | 管理员 | 删除账号 |
| GET | `/audit-logs` | 登录 | 审计日志 |
| GET | `/audit-logs/actions` | 登录 | 审计操作类型 |
| GET | `/audit-logs/stats` | 登录 | 审计行为统计（教师活跃度/操作分布/日趋势） |
| GET | `/platform/overview` | 超管 | 平台概览 |
| GET | `/platform/registration` | 超管 | 查询学生自助注册开关 |
| PUT | `/platform/registration` | 超管 | 设置学生自助注册开关（`{allow_registration: bool}`） |
| GET | `/platform/ai-credential` | 超管 | 查询 AI 服务凭证（只回掩码 `api_key_masked`，**绝不回明文密钥**） |
| PUT | `/platform/ai-credential` | 超管 | 保存 AI 服务凭证（`provider`/`base_url`/`model`/`api_key`/`vision_enabled`/`enabled`；`api_key` 留空＝保持原密钥，非空则 Fernet 加密覆盖） |
| POST | `/platform/ai-credential/test` | 超管 | AI 凭证连通性测试（发一次最小请求，允许「先测后存」；`api_key` 留空则回退已存密钥） |
| GET | `/platform/ai-grading` | 超管 | 查询 AI 批改开关（`enabled`/`auto_publish_excellent`/`daily_limit`/`max_tokens`/`configured`/`today_call_count` 当日用量）；`today_call_count` 取自平台级日计数表 `ai_usage_daily`，与批改结果行生命周期解耦 |
| PUT | `/platform/ai-grading` | 超管 | 设置 AI 批改开关（`{enabled, auto_publish_excellent, daily_limit(1-100000), max_tokens(64-32000)}`） |

## 八、其他

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/settings` | 管理员 | 系统设置 |
| PUT | `/api/settings/{key}` | 管理员 | 保存设置 |
| POST | `/api/settings/upgrade-grade` | 管理员 | 年级升级 |
| GET | `/api/stats/dashboard` | 教师+ | 看板统计 |
| GET | `/api/reports` | 登录 | 周报列表 |
| GET | `/api/reports/weekly-data` | 登录 | 周报聚合数据 |
| POST | `/api/reports` | 教师+ | 保存周报（含 id 时更新） |
| DELETE | `/api/reports/{id}` | 登录 | 删除周报 |
| POST | `/api/uploads` | 登录 | 通用文件上传 |
| GET | `/api/mobile/students` | 登录 | 移动端学生速查 |
| GET | `/api/mobile/students/{id}/overview` | 登录 | 移动端画像概览 |

## 九、运维与可观测性（非 `/api` 前缀）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/` | 公开 | 服务标识（版本/服务名） |
| GET | `/health` | 公开 | 健康检查，返回 `{"status": "ok"}` |
| GET | `/metrics` | 公开 | Prometheus 指标（请求数/状态码分布/耗时直方图/慢请求数/进行中请求数） |
| GET | `/docs` | 公开 | Swagger UI |
| GET | `/redoc` | 公开 | ReDoc |
| GET | `/openapi.json` | 公开 | OpenAPI schema |

> 访问日志：所有请求经 `app/observability.py` 的中间件记录 `方法 + 路径 + 状态码 + 耗时`，写入 `backend/logs/teachhub.log`（按天滚动、保留 30 天）；耗时 ≥ 1s 的请求标记 `[SLOW]` 并提升到 WARN 级别。

## 十、平台级全局配置（`settings` 表）

系统配置统一存于 `settings` 表，用 `school_id` 区分作用域：

| 作用域 | 判定 | 示例键 | 读写接口 |
| --- | --- | --- | --- |
| 校内配置 | `school_id = 本校 id` | `school_name`、`semester`、`grade`、`max_upload_size` | `GET /api/settings`、`PUT /api/settings/{key}`（学校管理员及以上） |
| 平台全局配置 | `school_id IS NULL` | `allow_registration` | `GET/PUT /api/admin/platform/registration`（仅平台超管） |
| 平台全局配置 | `school_id IS NULL` | `ai_grading_enabled`、`ai_auto_publish_excellent`、`ai_auto_publish_owner`、`ai_daily_call_limit`、`ai_max_tokens` | `GET/PUT /api/admin/platform/ai-grading`（仅平台超管）；凭证存 `ai_credentials` 表，走 `/api/admin/platform/ai-credential` |

> 读取统一走 `app/platform_settings.py`（`get_global_setting` / `set_global_setting` / `is_registration_allowed` / `is_ai_grading_enabled` 等）；该模块**所有查询显式 `skip_tenant_filter`**，因为全局配置行的 `school_id` 就是 `NULL`，在带租户上下文的请求里（如教师在带班级上下文中触发 AI 批改时读总开关与额度）不加此开关会**永远查不到**并静默落回默认值。
>
> **缺省值取向按功能分别约定**：学生自助注册 `allow_registration` 缺省 **开**（兼容引入开关之前的既有安装）；AI 批改相关开关缺省**一律关**（新功能默认不产生费用、不改动既有流程）。
>
> AI 批改相关键：`ai_grading_enabled`（平台级总开关，缺省关，关闭时**零外呼**且**触发接口返回 400**）、`ai_auto_publish_excellent`（优秀作品自动入库，缺省关＝推荐仅作候选待教师确认）、`ai_auto_publish_owner`（开启自动入库的超管 id，自动入库时计入 `excellent_works.selected_by`）、`ai_daily_call_limit`（每日调用上限，**平台级唯一成本刹车**，缺省 200）、`ai_max_tokens`（单次 max_tokens，缺省 1200）。
>
> **AI 批改触发点**：**仅** `POST /api/homework/assignments/{id}/ai-grade` 与 `POST /api/homework/submissions/{id}/ai-grade`
> （教师+，班级归属校验）。学生提交接口 `/assignments/{id}/submissions` **不做任何 AI 调用**。
> 学生重交时其提交的 AI 批改结果行被删除（旧结果只对旧版本内容成立）。

## 统一约定

- **分页**：`page`（默认 1）、`page_size`（默认 20，最大 200），返回 `{items, total}`
- **错误响应**：统一 `{detail: "中文提示"}`；状态码 400（参数）/ 401（未认证）/ 403（无权限）/ 404（不存在）/ 409（冲突）/ 413（文件过大）/ 422（校验）/ 423（锁定）/ 429（限流）/ 500（服务器错误）
- **学生语义**：所有业务表 `student_id` 均指向 `students.id`（学生档案），学生登录账号（`users.id`）通过「班级 + 姓名」软关联
- **多租户隔离**：由 **ORM 层事件统一按 `school_id` 隔离**（查询自动注入过滤、写入自动回填），平台超管（`school_id=NULL`）跨校
