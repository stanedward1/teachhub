# TeachHub API 接口文档

> 更新：2026-10-01 ｜ 前缀约定：所有接口以 `/api` 开头；作业平台以 `/api/homework` 为前缀；认证以 `/api/auth` 为前缀
>
> 认证方式：请求头 `Authorization: Bearer <token>`（登录/注册/注册开关状态/学校下拉/班级下拉/刷新令牌/登出/编程练习无需认证）。
> 令牌双轨：登录返回的访问令牌字段名为 `token`（短期有效，用于鉴权），另有 `refresh_token`（长期有效，用于换取新令牌对，详见「一、认证」末段）。
>
> 链路追踪：所有响应均带 `X-Request-ID` 响应头（请求头传入则透传，否则服务端生成 `uuid4`）；服务端日志每行带 `[rid=...]`，可用该 ID 串联同一请求的全部日志。
>
> 规模（2026-10-01 实测）：**业务接口 157 条**（`/api/**`）+ **7 条非业务路由**（`/openapi.json`、`/docs`、`/docs/oauth2-redirect`、`/redoc`、`/`、`/health`、`/metrics`），合计 **164 条带方法的已注册路由**。本文件所有计数均以 `len(app.routes)=165` 为分母核对：165 = 164 条带方法路由 + 1 个 `/uploads` 静态目录**挂载**（挂载不是路由，不并入接口计数）。

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
| POST | `/api/auth/login` | 公开 | 登录（限流 **30 次/分钟**，账号锁定 5 次/15 分钟）；返回 `{token, refresh_token, user, must_change_password}` |
| POST | `/api/auth/refresh` | 公开 | 用 `refresh_token` 换取新令牌对，返回 `{token, refresh_token, token_type}`（限流 120 次/分钟；失败返回 401） |
| POST | `/api/auth/logout` | 公开 | 撤销刷新令牌，返回 `{ok: true}`（幂等：重复调用仍返回成功；凭令牌本身即可调用，无需鉴权；限流 60 次/分钟） |
| POST | `/api/auth/register` | 公开 | 学生自助注册（限流 30 次/分钟；平台关闭注册时返回 403） |
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
| GET | `/api/meta/classes` | 公开 | 班级下拉（仅未毕业）。🔴 **必须传 `school_id`**：本端点无需登录，不传即返回**空列表** —— 否则会向匿名请求暴露**全部学校**的班级名称/代码/专业（跨租户泄露）。登录/注册页须先选定学校再拉取 |
| GET | `/api/meta/practice` | 公开 | 编程练习推荐 |

## 三、作业平台 `/api/homework`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/assignments` | 登录 | 作业列表（学生看本班；教师看自己负责班级 **+ 自己创建**的作业） |
| GET | `/assignments/{id}` | 登录 | 作业详情。**新增字段 `ai_companion_enabled`（布尔）**：平台级 AI 学伴开关，前端据此显隐学生端「AI 学伴」按钮（**经本端点下发，零新增端点、零额外往返**）。⚠️ 本端点依赖 `get_current_user`（**非** `require_student`）⇒ 教师/管理员亦可调用；但学伴**提问**端点另行挂 `require_student` |
| POST | `/assignments` | 教师+ | 布置作业 |
| PUT | `/assignments/{id}` | 教师+ | 编辑作业 |
| DELETE | `/assignments/{id}` | 教师+ | 删除作业 |
| GET | `/assignments/{id}/submissions` | 登录 | 提交列表（教师侧附 `ai_grading_status` / `ai_score` / `ai_excellent_candidate`，用于「AI 批改」按钮的结果反馈） |
| GET | `/assignments/{id}/unsubmitted` | 教师+ | 未交名单（应交 = 班级在籍学生，未交 = 应交 − 已交） |
| POST | `/assignments/{id}/ai-grade` | 教师+ | **触发 AI 批改（教师手动，批量）**：批改该作业下**尚未成功批改、且未在批改中**的提交；已批改（`success`）与**正在批改中（`pending`）**的一律跳过，剩余额度不足时按额度截断。返回 `{queued, skipped, already_graded, reason}`（全部已批改或全部在批改中 → **200** 且 `queued=0`，`reason` 区分「全部提交均已批改」/「其余提交正在批改中，请稍候」；`skipped` 恒为「未投递总数」）。**2026-10-08 修复：此前只剔除 `success`，教师双击会在后端非阻塞返回后二次投递 → 重复外呼 + 重复预扣配额。**非阻塞（仅入队）。400 档位：平台开关关「AI 批改总开关未开启」/ **学校闸关「本校已停用 AI 批改功能」** / 无凭证 / **校池尽「本学校今日 AI 批改次数已用完（今日已用 X 次），请明天再试」** / 平台池尽 |
| GET | `/assignments/{id}/ai-grade/progress` | 教师+ | **查询某作业批量 AI 批改进度**（前端轮询用）。返回 `{total, success, failed, pending, ungraded, done, finished}`：`done = success + failed`，`ungraded = total − success − failed − pending`。终止字段 `finished = (pending == 0)`（表示「没有在跑的任务了」，**不是** `done == total`——额度截断时会出现 `ungraded > 0` 但 `pending == 0`，此时即应停止轮询并如实展示「还有 N 份未批改」）。纯聚合、无写操作、无外呼。作业不存在 → 404，非本班且非创建者教师 → 403 |
| POST | `/assignments/{id}/companion/ask` | **学生** | **AI 学伴提问（学生专属，同步阻塞，超时 25s）**。请求体仅 `{"question": str}`（**走 `AiCompanionAsk` schema**：字段缺省/null → service 层 400；非字符串 → 422；长度 1..1500 在 service 层校验）；**题干 / 历史 / 开关一律由服务端自取**，前端禁止传入。成功返回 `{conversation_id, answer, refused, turns, truncated}`。⚠️ **无幂等性**：同一次提问重试会**再消耗 1 次学伴额度**。**双闸门**（每生配额 + 平台池，叠加生效）：每生配额耗尽 → **429**「你今天使用 AI 学伴的次数已用完，明天再来吧」；平台池耗尽（每生仍有余）→ **429**「AI 学伴今天实在太忙了，明天再来试试吧」（**不向学生泄露平台成本口径**）。**校级闸门叠加后为三闸**（每生 → 学校 → 平台）：**学校闸关 → 403**「AI 学伴在你所在的学校暂未开放」；**学校池尽 → 429**（与平台池共用「太忙了」同款文案，不区分层级）。开关关 `ai_companion_enabled`（平台或本校任一关） → **403**（零外呼）；作业不存在 → **404**；非本班学生 → **403**；提问为空 / 超 1500 字 → **400**；无可用凭证 → **503**；模型调用失败 / 被截断 → **502**（两种差异化文案）。`refused=true` 时 `answer` 是**标准引导话术**（非模型原文）。教师调用 → **403** |
| GET | `/assignments/{id}/companion/history` | **学生** | **取本学生在该作业下的学伴会话历史**。返回 `{conversation_id, turns, messages: [{id, role, content, refused, created_at}]}`（`role` = `user` / `assistant`，`created_at` 为 ISO 字符串）。**无会话时 `conversation_id=null` + 空数组（不 404）**；开关关闭时同样返回空历史（不 403），前端首屏不报错。作业不存在 → 404；非本班学生 → 403 |
| GET | `/assignments/{id}/companion/quota` | **学生** | **取本学生今日的学伴额度读数**（每生独立配额，docs/DESIGN-AI学伴配额.md D4）。只读、无副作用。返回 `{enabled: bool, remaining: int, limit: int, used: int, day: "YYYY-MM-DD"}`（**`remaining = min(每生剩余, 学校剩余, 平台池剩余)`**——三池取最小才是真实可问次数，平台池耗尽时显示 0（2026-10-01 修订，此前不并入平台池）；`limit`/`used` 仍为每生口径；开关关闭时 `remaining=0`）。**`day` 已 `stringify_dates`**（硬约束：否则 Pydantic v2 在落库后抛错 → 500）。学生端抽屉打开 / 提问成功后调用，显示「今日剩余 N 次」（**重拉权威值，不本地减一**）。🔴 只挂 `require_student`：教师调用 → **403**。作业不存在 → **404**；非本班学生 → **403** |
| DELETE | `/assignments/{id}/companion` | **学生** | **清空本学生在该作业下的学伴会话消息**。返回 `{deleted: int}`（删除的消息条数）。**只删本会话**（`school_id` 由 ORM 过滤），**不影响额度**（额度是平台级外呼计数，与消息行生命周期解耦）。作业不存在 → 404；非本班学生 → 403 |
| GET | `/assignments/{id}/companion/conversations` | **教师（仅）** | **列出该作业下本班学生的学伴会话**（一个学生会话 = 一行，**不含消息内容**）。分页 `page` / `page_size`（默认 20），返回 `{items: [{conversation_id, student_id, student_name, student_avatar, class_id, turn_count, refused_count, has_refused, last_active_at}], total}`。权限口径 = 班主任 ∪ 科任（`apply_teacher_student_filter` 统一收口），作业级入口另放行**该作业创建者**（「创建者保留管理权」，2026-10-09）。**管理员（school_admin / super_admin）本轮不放行 → 403**（路由依赖 `require_teacher_only`）。非本班且非创建者 → 403；创建者若已不带该班，则学生范围为空 ⇒ **200 且 `items=[]`**（放行 ≠ 泄露）；作业不存在 → 404。审计 action = `companion_view_list` |
| GET | `/companion/conversations/{conversation_id}` | **教师（仅）** | **取单个学伴会话的完整消息**（含**学生提问原文 + AI 全文**；仅元数据无法判断学生卡在哪）。返回 `{conversation_id, student_id, student_name, assignment_id, assignment_title, messages: [{id, role, content, refused, created_at}], turns}`。🔴 **三重硬校验**：① 会话存在；② 其作业本班可访问（或系该教师所创建）；③ 该会话 `student_id` 落在教师可见班级范围内。**任一不满足一律 404**（不泄露会话存在性；跨校、跨班、越权均为 404，**非 403**）。管理员本轮不放行 → 403（`require_teacher_only`）。教师侧**只读**，无任何写端点。审计 action = `companion_view_detail` |
| POST | `/assignments/{id}/submissions` | 学生 | 提交作业（**不触发任何 AI 调用**） |
| GET | `/submissions/{id}` | 登录 | 提交详情（含 `assignment_title` + 点评 + 评优信息 excellent_id/excellent_note + AI 批改 `ai_grading`）。AI 结果**仅本人可见**（学生读他人提交 403）；学生侧**不含** `error`（失败原因只给教师） |
| POST | `/submissions/{id}/ai-grade` | 教师+ | **触发 AI 批改（教师手动，单份）**：已有 `success`/`failed` 结果则重跑覆盖（用于补批失败件或重交后重批；前端对 `success` 重批做**二次确认**，因会再消耗一次额度）。🔴 **该提交已在批改中（`pending`）→ 幂等空操作返回 200**（`{queued:0, skipped:1, already_graded:0, reason:"该提交正在批改中，请稍候"}`），不重复外呼、不重复预扣配额（2026-10-08 修复，防教师双击 / 多标签页）。正常返回 `{queued, skipped, reason}`。开关关（平台/本校）/ 无凭证 / 额度耗尽（校池/平台池）→ 400（文案同批量入口）；提交**正文与附件路径均为空**（确实无可评内容）→ 400「提交无可评内容（正文与附件均为空）」，且**不占用额度**（同时落一条 `failed` 解释行供教师查看，避免其停在 `ungraded`） |
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
| PUT | `/api/students/password/batch` | 登录 | **批量**重置/修改学生密码（body `{student_ids:[int], password?:str}`，留空=默认 123456）；不存在/无权限/已退学的目标**跳过**并计入 `failed`，返回 `{ok, updated, failed:[{id,reason}]}` |
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
| GET/POST | `/api/resources` | 教师+ | 资源列表/新增。🔴 新增时**平台超管必须显式传 `school_id`**（缺 → 400「请选择学校」；学校不存在 → 400「学校不存在」）；教师/校管**忽略入参**，一律归属自己学校。原因：本表**无父资源**可继承，超管上下文 `school_id=None` 会让行落 NULL ⇒ 全租户不可见 |
| DELETE | `/api/resources/{id}` | 教师+ | 删除资源 |
| GET | `/api/exams` | 教师+ | 试卷列表 |
| POST | `/api/exams/upload` | 教师+ | 上传试卷（**querystring** 可选 `school_id`）。🔴 归属规则同资源表：**超管必须显式指定**（缺/不存在 → 400）；教师/校管忽略入参、归属自己学校。依赖 `require_teacher`（= `dep`），与 `/resources` 及兄弟端点同权（学生 403） |
| PUT | `/api/exams/{id}` | 教师+ | 修改试卷 |
| GET | `/api/exams/{id}/download` | 教师+ | 下载试卷 |
| DELETE | `/api/exams/{id}` | 教师+ | 删除试卷 |
| GET | `/api/seats` | 登录 | 座位表查询 |
| PUT | `/api/seats` | 登录 | 保存座位表 |
| GET | `/api/import-history` | 登录 | 导入历史 |

## 六、班级日志

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET/POST | `/api/work-logs` | 登录/教师+ | 工作日志列表/新增。🔴 新增时**平台超管必须显式传 `school_id`**（缺 → 400「请选择学校」；学校不存在 → 400「学校不存在」）；教师/校管**忽略入参**，一律归属自己学校。原因：本表**无父资源**可继承，超管上下文 `school_id=None` 会让行落 NULL ⇒ 全租户不可见 |
| PUT/DELETE | `/api/work-logs/{id}` | 登录 | 日志修改/删除 |
| GET/POST | `/api/class-plans` | 登录/教师+ | 班级计划列表/新增。🔴 归属规则同 `/api/work-logs`（超管新增须显式 `school_id`） |
| PUT/DELETE | `/api/class-plans/{id}` | 登录 | 计划修改/删除 |
| GET/POST | `/api/teacher-plans` | 登录/教师+ | 个人计划列表/新增。🔴 归属规则同 `/api/work-logs`（超管新增须显式 `school_id`） |
| PUT/DELETE | `/api/teacher-plans/{id}` | 登录 | 计划修改/删除 |
| GET/POST | `/api/schedules` | 登录 | 课表 |
| PUT | `/api/schedules/{id}` | 登录 | 修改课表 |
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
| GET | `/platform/student-device` | 超管 | 查询学生「单设备在线」开关（缺省 **开启**） |
| PUT | `/platform/student-device` | 超管 | 设置学生「单设备在线」开关（`{student_single_device: bool}`）；开启后学生登录会作废该账号此前的**全部**会话 —— 后登录挤掉先登录 |
| GET | `/platform/ai-credential` | 超管 | 查询 AI 服务凭证（只回掩码 `api_key_masked`，**绝不回明文密钥**） |
| PUT | `/platform/ai-credential` | 超管 | 保存 AI 服务凭证（`provider`/`base_url`/`model`/`api_key`/`vision_enabled`/`enabled`；`api_key` 留空＝保持原密钥，非空则 Fernet 加密覆盖） |
| POST | `/platform/ai-credential/test` | 超管 | AI 凭证连通性测试（发一次最小请求，允许「先测后存」）。🔴 **两条路径**（2026-10-08 修复）：请求体带自定义 `base_url` + `model` 时**必须同时自带 `api_key`**，`api_key` 留空 → 直接返回 `ok=false`、**绝不外呼**（此前会回退库内已存密钥 ⇒ 持超管 JWT 者可把平台密钥发往请求体指定的任意主机，构成密钥外泄 + SSRF）；请求体为空 → 用**已存配置**测试。**不回显密钥** |
| GET | `/platform/ai-grading` | 超管 | 查询 AI 批改开关（`enabled`/`auto_publish_excellent`/`daily_limit`/`max_tokens`/`configured`/`today_call_count` 当日用量）；`today_call_count` 取自平台级日计数表 `ai_usage_daily`，与批改结果行生命周期解耦 |
| PUT | `/platform/ai-grading` | 超管 | 设置 AI 批改开关（`{enabled, auto_publish_excellent, daily_limit(1-100000), max_tokens(64-32000)}`） |
| GET | `/schools/{school_id}/ai-settings` | 超管 | **读取校级 AI 能力配置合并视图**（`require_super_admin`）。学校不存在 → 404「学校不存在」；非超管 → 403。返回**四段结构**（`day` 已 `stringify_dates`）：`platform`（平台当前值：批改/学伴 开关+每日上限）、`school_override`（4 个 key 的**原始覆盖值**，字符串，无行 = `null`）、`effective`（合并生效值：开关 = 平台 AND 学校；池 = 校级覆盖，`null` = 不限）、`usage_today`（`{day, grading: {used, school_limit}, companion: {used, school_limit}}`，校池今日用量 + 校池上限回显） |
| PUT | `/schools/{school_id}/ai-settings` | 超管 | **保存校级 AI 能力配置**（body：`{grading_enabled?, grading_daily_limit?, companion_enabled?, companion_daily_limit?}`，全部可省）。**部分更新三态语义**：字段**未传** = 不动；显式 **null** = 删对应 school 级行（清除覆盖：开关恢复跟随平台闸、上限恢复「不限」）；显式**值** = 写入覆盖（开关 true/false；数值 ≥ 0，`0` 合法，bool 冒充数值或负数 → 400）。空 body `{}` → 200 且零变化。写库 + 审计（action `update_school_ai_settings`，detail 只记变更字段名不记值）同事务原子，响应返回与 GET 相同的四段合并视图 |

> **校级 AI 配置键**（存 `settings` 表 school 级行，复用 `(school_id, key)` 唯一约束；**缺省语义 = 未配置行即跟随平台**：开关缺省**开**、上限缺省**不限**，「关」必须显式落行）：
>
> | key | 类型 | 语义 | 缺省（无行） |
> | --- | --- | --- | --- |
> | `school_ai_grading_enabled` | bool 字符串（`"1"`/`"0"`） | 本校 AI 批改开关 | 开（跟随平台闸） |
> | `school_ai_companion_enabled` | bool 字符串 | 本校 AI 学伴开关 | 开（跟随平台闸） |
> | `school_ai_grading_daily_limit` | int 字符串 | 本校批改每日调用次数上限（校池） | 不限（不设校池） |
> | `school_ai_companion_daily_limit` | int 字符串 | 本校学伴每日调用次数上限（校池） | 不限（不设校池） |
>
> 上限值为 `"0"` = 合法配置（今日 0 次，等效停用该池）；空串/非法/负值 = 不限（fail-open 与缺省一致）。两校池计数表：`ai_usage_daily_school` / `ai_usage_daily_companion_school`（唯一 `(day, school_id)`，均为 `schools.id` 外键）。🔴 防线：校内管理员经 `PUT /api/settings/{key}` 写 `school_` 前缀 key → **400**（黑名单，豁免既有 legacy key `school_name`）。

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

> **接口对账口径**：`backend/_api_diff.py` 以 **`/api` 业务接口**为基准（取 `app.routes` 中路径以 `/api` 开头、且带方法者）。因此本节 6 条非 `/api` 端点（`/`、`/health`、`/metrics`、`/docs`、`/redoc`、`/openapi.json`）会被脚本列为「API.md 有、代码无」——这是**预期正确现象**（它们本就不在 `/api` 前缀内，只是脚本的比对维度不覆盖），**无需修改**。对账结论：`/api` 业务接口**漏列 = 0**（2026-09-29 实测）。
>
> 访问日志：所有请求经 `app/observability.py` 的中间件记录 `方法 + 路径 + 状态码 + 耗时`，写入 `backend/logs/teachhub.log`（按天滚动、保留 30 天）；耗时 ≥ 1s 的请求标记 `[SLOW]` 并提升到 WARN 级别。

## 十、平台级全局配置（`settings` 表）

系统配置统一存于 `settings` 表，用 `school_id` 区分作用域：

| 作用域 | 判定 | 示例键 | 读写接口 |
| --- | --- | --- | --- |
| 校内配置 | `school_id = 本校 id` | `school_name`、`semester`、`grade`、`max_upload_size` | `GET /api/settings`、`PUT /api/settings/{key}`（学校管理员及以上） |
| 平台全局配置 | `school_id IS NULL` | `allow_registration`、`student_single_device` | `GET/PUT /api/admin/platform/registration`、`GET/PUT /api/admin/platform/student-device`（仅平台超管）；`student_single_device` 缺省 **开**：学生每次登录都会作废该账号此前的全部会话（`token_version` 自增 + 撤销未撤销的 refresh token），仅约束 `role=student` |
| 平台全局配置 | `school_id IS NULL` | `ai_grading_enabled`、`ai_auto_publish_excellent`、`ai_auto_publish_owner`、`ai_daily_call_limit`、`ai_max_tokens` | `GET/PUT /api/admin/platform/ai-grading`（仅平台超管）；凭证存 `ai_credentials` 表，走 `/api/admin/platform/ai-credential` |
| 平台全局配置 | `school_id IS NULL` | `ai_companion_enabled`、`ai_companion_daily_limit`、`ai_companion_per_student_daily_limit` | 复用 `GET/PUT /api/admin/platform/ai-grading`（仅平台超管，与上一行**同端点**）。🔴 **与 AI 批改分开控制**：`ai_companion_enabled` 缺省**关**；`ai_companion_daily_limit`（**平台池**，全平台成本刹车）缺省 **6000**，使用**独立计数表 `ai_usage_daily_companion`**（与批改的 `ai_usage_daily` 互不挤占，两把行锁互不阻塞）；`ai_companion_per_student_daily_limit`（**每生独立配额**，公平刹车）缺省 **20**，使用**独立计数表 `ai_companion_usage_daily_student`**（唯一约束 `(day, student_id)`）。**两层额度叠加生效（双闸门）**：任一耗尽都 429，先触发的先拦 |
| 校级 AI 配置（校级覆盖层） | `school_id = 本校 id` | `school_ai_grading_enabled`、`school_ai_companion_enabled`、`school_ai_grading_daily_limit`、`school_ai_companion_daily_limit` | `GET/PUT /api/admin/schools/{school_id}/ai-settings`（仅平台超管，见「七、系统管理」表后说明）。**开关语义 = 平台闸 × 学校闸（AND），学校闸缺省开**（无行 = 跟随平台闸）；**额度 = 学校池 + 平台池双闸门**（学伴另有每生闸，三闸：每生 → 学校 → 平台），按**调用次数**计。🔴 校内 `PUT /api/settings/{key}` 写 `school_` 前缀 key → 400（黑名单，豁免既有 `school_name`） |

> 读取统一走 `app/platform_settings.py`（`get_global_setting` / `set_global_setting` / `is_registration_allowed` / `is_ai_grading_enabled` 等）；该模块**所有查询显式 `skip_tenant_filter`**，因为全局配置行的 `school_id` 就是 `NULL`，在带租户上下文的请求里（如教师在带班级上下文中触发 AI 批改时读总开关与额度）不加此开关会**永远查不到**并静默落回默认值。
>
> **缺省值取向按功能分别约定**：学生自助注册 `allow_registration` 缺省 **开**（兼容引入开关之前的既有安装）；学生「单设备在线」`student_single_device` 缺省 **开**（产品要求「后登录挤掉先登录」，关闭只为留运维退路，例如联调需同时保留多个学生会话）；AI 批改相关开关缺省**一律关**（新功能默认不产生费用、不改动既有流程）。
>
> ⚠️ `student_single_device` 走通用 `to_bool(default=True)`（**不是** `is_registration_allowed` 那种「配置缺失 ⇒ True」的特例），因此显式写入的假值集（`0/false/no/off`）同样能关闭它 —— 「一键关掉」的退路不会被「缺省 True」的实现细节吃掉。
>
> AI 批改相关键：`ai_grading_enabled`（平台级总开关，缺省关，关闭时**零外呼**且**触发接口返回 400**）、`ai_auto_publish_excellent`（优秀作品自动入库，缺省关＝推荐仅作候选待教师确认）、`ai_auto_publish_owner`（开启自动入库的超管 id，自动入库时计入 `excellent_works.selected_by`）、`ai_daily_call_limit`（每日调用上限，**平台级唯一成本刹车**，缺省 200）、`ai_max_tokens`（单次 max_tokens，缺省 **2048**）。⚠️ **推理模型的思考 token 与正文共用这份预算**：`deepseek-flash` 等推理模型思考模式默认打开，预算偏小时会返回「`finish_reason=length` 且正文为空」；故批改侧显式下发`thinking.type=disabled`（配置项 `AI_THINKING_MODE`），并带一次截断重试（`min(max_tokens×3, AI_MAX_TOKENS_CEILING)`）。另：上表「配置默认值」只在 `settings` 表无对应行时生效 —— **DB 行优先**，改 `config.py` 不会影响已存 `ai_max_tokens` 的部署。
>
> **AI 批改触发点**：**仅** `POST /api/homework/assignments/{id}/ai-grade` 与 `POST /api/homework/submissions/{id}/ai-grade`
> （教师+，班级归属校验）。学生提交接口 `/assignments/{id}/submissions` **不做任何 AI 调用**。
> 学生重交时其提交的 AI 批改结果行被删除（旧结果只对旧版本内容成立）。
>
> **AI 学伴（学生端引导式问答）**：学生侧 **4 端点**（`ask` / `history` / `quota` / `clear`，均 `require_student`）+ 教师侧 **2 端点**（会话列表 / 会话详情，均 `require_teacher_only`，**只读**）。
> 链路：`POST /assignments/{id}/companion/ask` 由后端**自取**题干与附件（不信任前端上下文），**原子预留独立学伴额度**后同步调用模型（`AI_COMPANION_TIMEOUT=25`，**< 前端 axios 30s**，留 5s 缓冲）。
> **额度双闸门**：**每生独立配额**（`ai_companion_per_student_daily_limit`，缺省 20，公平语义）与**平台池**（`ai_companion_daily_limit`，缺省 6000，成本语义）**叠加生效**，任一耗尽都 429；闸门顺序「先每生、后平台池」决定 429 文案（个人 vs 平台）。两层用**独立计数表、独立行锁**，互不阻塞、互不污染。额度**只增不减**（外呼失败不退还）。
> 护栏为**引导式 + V1 启发式**（长代码块替换为引导话术），**属启发式、非保证**，命中率 / 误杀率须由抽检建立基线。
> 关闭 `ai_companion_enabled` 时学伴链路**零外呼**（提问 403），学生端按钮隐藏（**非置灰**）。

## 统一约定

- **分页**：`page`（默认 1）、`page_size`（默认 20，最大 200），返回 `{items, total}`
- **错误响应**：统一 `{detail: "中文提示"}`；状态码 400（参数）/ 401（未认证）/ 403（无权限）/ 404（不存在）/ 409（冲突）/ 413（文件过大）/ 422（校验）/ 423（锁定）/ 429（限流）/ 500（服务器错误）
- **学生语义**：所有业务表 `student_id` 均指向 `students.id`（学生档案），学生登录账号（`users.id`）通过「班级 + 姓名」软关联
- **多租户隔离**：由 **ORM 层事件统一按 `school_id` 隔离**（查询自动注入过滤、写入自动回填），平台超管（`school_id=NULL`）跨校
