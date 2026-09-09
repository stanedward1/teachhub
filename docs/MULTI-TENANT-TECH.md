# TeachHub 多租户 SaaS 技术方案

> 版本：v1.0 ｜ 日期：2026-09-07 ｜ 状态：已实现（2026-09-08）
> 关联文档：[产品需求](MULTI-TENANT-PRD.md)

---

## 1. 多租户架构选型

| 方案 | 隔离方式 | 优点 | 缺点 | 适用 |
| ---- | ---- | ---- | ---- | ---- |
| A. 共享库 + 共享 Schema | `school_id` 列隔离 | 成本最低、运维简单、迁移平滑 | 隔离依赖代码纪律 | ✅ **本次选型** |
| B. 共享库 + 独立 Schema | 每租户一个 schema | 隔离更硬、可独立备份 | 迁移/连接管理复杂，SQLAlchemy 适配成本高 | 租户少且要求强隔离 |
| C. 独立数据库 | 每租户一个库 | 最强隔离 | 运维成本高、跨库统计困难 | 大客户/合规强要求 |

**选型结论**：采用 **方案 A（共享库 + 共享 Schema + `school_id` 列隔离）**，理由：

1. 中职学校单校数据量小（每校几百到几千学生），单库完全承载；
2. 现有 `schools` / `classrooms.school_id` / `students.school_id` 已具备雏形，改造平滑；
3. 一套 SQLAlchemy 连接即可，无动态 schema/库切换复杂度；
4. 通过 `school_id` 抽象，未来可平滑升级到方案 B/C（分库分表）。

---

## 2. 数据模型改造

### 2.1 角色重构

`users.role` 取值由 `student / teacher / admin` 扩展为：

| role | 含义 | school_id |
| ---- | ---- | ---- |
| `super_admin` | 平台超管（原 admin 语义） | `NULL` |
| `school_admin` | 学校管理员（新增） | 必填 |
| `teacher` | 教师（班主任/科任） | 必填 |
| `student` | 学生 | 必填 |

> 兼容策略：迁移时原 `admin` 统一改为 `super_admin`；代码中 `role == "admin"` 的判断需改为 `role in ("super_admin", "school_admin")` 或提供 `is_admin()` 辅助函数。

### 2.2 核心表加 `school_id`

| 表 | 改动 | 说明 |
| ---- | ---- | ---- |
| `users` | **+ school_id**（FK schools，可空，super_admin 为 NULL） | 用户归属租户 |
| `schools` | + `status`（active/disabled，默认 active）；+ `created_by` | 租户状态 |
| `classrooms` | 已有 school_id | 保持 |
| `students` | 已有 school_id | 保持 |

### 2.3 业务表冗余 `school_id`

以下业务表**全部新增 `school_id` 列**（直接冗余，确保隔离严密 + 查询无需 join）：

| 域 | 表 |
| ---- | ---- |
| 作业 | `assignments`、`submissions`、`submission_comments`、`excellent_works`、`work_comments` |
| 工作台 | `scores`、`leaves`、`points`、`communications`、`performances`、`talks`、`return_records`、`student_comments`、`student_profile_tags`、`student_board_history`、`attendance`、`weekly_reports`、`seats`、`resources`、`exams` |
| 日志 | `work_logs`、`class_plans`、`teacher_plans`、`schedules`、`activities` |
| 其他 | `import_history`、`operation_logs` |

> `class_teachers` 通过 `class_id` 关联班级即可推导学校，不冗余（关联表只含外键）。

### 2.4 唯一约束调整

- **教师用户名**：原 `users.username` 全局唯一 → 改为 **`(school_id, username)` 学校内唯一**（不同学校可同名教师）。
- 学生账号定位：原「`class_id + name`」升级为「`school_id + class_id + name`」。

### 2.5 索引

- 所有含 `school_id` 的业务表建索引：`ix_<table>_school_id`。
- 高频组合索引：`(school_id, class_id)`、`(school_id, student_id)`、`(school_id, created_at)`。

---

## 3. 数据库迁移方案

新增 Alembic 迁移（在 `b6d5e4f3a2c1` 之后），分两步：

### 迁移 1：加列 + 回填默认租户

```python
# upgrade 伪代码
# 1. 确保默认租户存在（取现有 schools 第一条，或创建「默认学校」）
default_school_id = <现有学校 ID>

# 2. users 加 school_id 列（nullable），super_admin 为 NULL，其余回填 default_school_id
# 3. schools 加 status、created_by 列
# 4. 各业务表加 school_id 列，并回填：
#    - 通过 student/classroom 关联回填，或直接回填 default_school_id
# 5. role 迁移：admin → super_admin
# 6. 唯一约束：删 users.username 唯一，改 (school_id, username) 联合唯一
```

### 迁移 2：收紧非空

- 回填完成后，将 `school_id` 列改为 `nullable=False`（super_admin 的 `users.school_id` 除外，保持可空）。

> 迁移必须**可重复、可回滚**，并在空库场景（全新部署）下同样成立：全新部署时默认无数据，`school_id` 直接在 `create_all`/迁移中定义非空即可。

---

## 4. 租户上下文与隔离实现

### 4.1 租户上下文

JWT payload 增加 `school_id`（`create_access_token` 时写入）：

```python
# security.py
def create_access_token(subject: str, role: str, school_id: int | None = None) -> str:
    payload = {"sub": subject, "role": role, "school_id": school_id}
    ...
```

`get_current_user` 解析 JWT 后，返回的 `user` 对象携带 `school_id`。

### 4.2 查询过滤（隔离核心）

**原则：任何涉及租户数据的查询，必须带 `school_id` 过滤。**

- 新增辅助函数（`permissions.py`）：

```python
def ensure_same_school(user, target_school_id: int | None):
    """校验目标资源属于当前用户学校，否则 403/404。"""

def get_user_school_id(user) -> int | None:
    """返回用户的学校 ID（super_admin 返回 None，表示不限制）。"""
```

- 各 Router 的查询改造示例：

```python
# 原：db.query(Score).filter(Score.student_id == sid)
# 改：db.query(Score).filter(Score.school_id == user.school_id, Score.student_id == sid)

# 原：db.query(Classroom).filter(...)
# 改：db.query(Classroom).filter(Classroom.school_id == user.school_id, ...)
```

- **越权拦截**：按 ID 取资源（`db.get(Score, id)`）后，必须校验 `resource.school_id == user.school_id`，否则抛 `404`（不暴露存在性）或 `403`。

### 4.3 权限函数升级

`permissions.py` 现有函数需增加 `school_id` 维度：

| 函数 | 改造 |
| ---- | ---- |
| `get_teacher_class_ids(db, user)` | 内部 `Classroom.school_id == user.school_id` 过滤 |
| `is_teacher_class_owner(db, user, class_id)` | 校验班级属于本校 |
| `filter_classrooms_by_teacher` / `filter_students_by_teacher` | 加 `school_id` 过滤 |

### 4.4 角色判断辅助

```python
def is_platform_admin(user) -> bool:   # role == "super_admin"
def is_school_admin(user) -> bool:     # role == "school_admin"
def is_any_admin(user) -> bool:        # super_admin 或 school_admin
```

---

## 5. 登录改造

### 5.1 登录请求

`LoginRequest` 增加 `school_id` 字段：

```python
class LoginRequest(BaseModel):
    username: str          # 学生=姓名，教师/管理员=用户名
    password: str
    class_id: int | None   # 学生登录
    school_id: int | None  # 新增：学校 ID（学生/教师/学校管理员登录必填）
```

### 5.2 登录逻辑

```python
# super_admin：无 school_id，全局唯一用户名
# school_admin / teacher：school_id + username 定位
# student：school_id + class_id + name 定位
```

- 平台超管登录：`username + password`（school_id 为空）。
- 其他账号登录：`school_id + (username | class_id+name) + password`。
- 校验 `schools.status == "active"`，停用学校拒绝登录。

### 5.3 前端登录页

- 学生/教师登录页增加「选择学校」下拉（或记住上次学校）。
- 平台超管走独立入口（`/platform/login`）或自动识别。

---

## 6. 关键代码改造清单

| 文件 | 改造内容 |
| ---- | ---- |
| `models/user.py` | User 加 `school_id`，role 注释更新 |
| `models/school.py` | School 加 `status`、`created_by` |
| `models/*.py` | 业务表加 `school_id` 列 |
| `security.py` | JWT 加 `school_id`；`create_access_token` 签名更新 |
| `deps.py` | `get_current_user` 解析 school_id；新增 `require_school_admin` / `require_super_admin` 依赖 |
| `permissions.py` | 权限函数加 school_id 维度；新增 `ensure_same_school` / `get_user_school_id` |
| `auth.py` | 登录逻辑改造（学校维度 + 停用学校拦截） |
| `students.py` | 学校/班级/学生 CRUD 加 school_id 过滤；新增学校管理员管理入口 |
| `workbench.py` / `classlog.py` / `homework.py` / `attendance.py` / `mobile.py` / `admin.py` | 所有查询/写入加 school_id 过滤 |
| `audit.py` | audit 记录 school_id |
| `seed.py` | 生成默认租户 + 各角色示例账号 |
| 前端 `Login.vue` 等 | 登录页加学校选择；`auth` 工具存 school_id |

---

## 7. 安全设计

1. **双重隔离**：接口层（权限依赖 + 查询过滤）+ 数据层（school_id 列），任一层失效不泄露。
2. **越权返回 404**：跨学校按 ID 访问，返回 404（不暴露资源存在性）。
3. **审计贯穿**：`operation_logs` 记录 `school_id`，平台超管可全局审计，学校管理员仅本校。
4. **账号安全沿用**：登录锁定、密码强度、首次改密在多租户下继续生效，且按「学校维度」统计。
5. **敏感字段**：`password_hash` 永不下发；上传文件路径隔离（未来可 `uploads/<school_id>/...`）。

---

## 8. 性能与扩展

- 所有租户查询走 `school_id` 索引。
- 预留分库：`school_id` 作为分片键，未来可 `DATABASE_URL` 按租户路由到独立库（方案 C）。
- 平台超管跨校统计使用聚合查询（`GROUP BY school_id`）。

---

## 9. 实施步骤

| 步骤 | 内容 |
| ---- | ---- |
| 1 | 模型 + 迁移（加列、回填、角色迁移），本地验证空库/存量库两条路径 |
| 2 | 租户上下文（JWT + deps + permissions），单元测试隔离 |
| 3 | 登录改造（前端学校选择 + 后端学校维度登录） |
| 4 | 各 Router 逐模块加 school_id 过滤，回归测试 |
| 5 | 学校管理员工作台 + 平台超管学校管理 UI |
| 6 | 安全审计（越权测试矩阵）+ 文档更新 + 上线 |

---

## 10. 风险与回滚

| 风险 | 缓解 |
| ---- | ---- |
| 隔离遗漏（某查询忘加 school_id） | 代码评审清单 + 越权自动化测试覆盖所有模块 |
| 存量数据回填错误 | 迁移分两步（先加列回填，再收紧非空），回填后数据校验 |
| 唯一约束调整导致登录异常 | 迁移前备份；`(school_id, username)` 联合唯一兼容单校场景 |
| 性能下降 | 全量 `school_id` 索引 + 组合索引 |
