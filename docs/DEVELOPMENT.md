# TechHub 开发规范

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
cd techhub
docker compose up -d --build  # 构建并启动前后端
docker compose logs -f backend
docker compose down           # 停止
```

### 1.5 测试

```bash
cd backend
python -m pytest tests/ -v
```

## 2. 配置管理

- 所有环境相关配置走 `.env`（`backend/.env`，模板见 `.env.example`），**严禁硬编码密钥**。
- `.env` 已加入 `.gitignore`，不得提交。
- 生产环境必须覆盖 `SECRET_KEY`（随机 32+ 字节）。

| 变量 | 说明 | 默认 |
| ---- | ---- | ---- |
| `DATABASE_URL` | 数据库连接串 | `sqlite:///./techhub.db` |
| `SECRET_KEY` | JWT 签名密钥 | 开发默认值（**生产必改**） |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token 有效期 | `1440`（24 小时） |
| `MAX_UPLOAD_SIZE` | 上传文件大小上限 | `20971520`（20MB） |

## 3. 后端代码规范

### 3.1 结构约定

- 模型按**业务域**拆分到 `models/` 下独立文件，统一在 `models/__init__.py` 导出。
- 路由按**业务域**拆分到 `routers/`，一个域一个文件。
- 新增路由文件后需在 `main.py` 中 `include_router`。

### 3.2 请求/响应

- 认证相关接口使用 `schemas.py` 中的 Pydantic 模型做校验。
- 其余 CRUD 使用 `payload: dict` + `.get()`，逐步迁移到 Pydantic schema。
- 错误统一抛 `HTTPException(status_code, detail)`，`detail` 使用中文、面向用户。

### 3.3 权限

- 只读接口用 `Depends(get_current_user)`；写接口按角色挂 `Depends(require_teacher)` / `require_school_admin` / `require_super_admin`，学生端写接口挂 `require_student`。
- 任何新增管理端接口**必须**挂 `require_teacher`（教师及以上）；平台级能力（学校开通/启停、跨校概览）挂 `require_super_admin`。
- **多租户隔离（必须）**：所有涉及租户数据的查询/写入必须带 `school_id`。ORM 层已通过 `app/tenant.py` 全局自动隔离（`do_orm_execute` 注入 `school_id` 过滤 + `before_flush` 回填），平台超管（`school_id=NULL`）不受限；跨校按 ID 访问应返回 404（不泄露存在性）。角色判断用 `permissions.is_any_admin()`（本校全量）/ `is_platform_admin()`（跨校），**不要**直接比较 `user.role == "admin"`。
- 教师班级数据隔离**统一**走 `permissions.get_teacher_class_ids()` / `is_teacher_class_owner()`，这两个函数已支持「班主任 + 科任老师」多教师模型；**不得**直接比较 `Classroom.teacher_id` 做权限判断，否则会漏掉科任老师。

### 3.4 模型变更

- 新增字段/表：修改模型定义后，必须配套新增 Alembic migration（`backend/alembic/versions/`）
- 生成迁移脚本：`cd backend && alembic revision --autogenerate -m "描述"`，人工核对后提交
- 应用到本地库：`alembic upgrade head`（本地启动或 Docker 启动会自动执行）
- 确保「迁移链」与「模型 schema」保持一致，避免依赖 `create_all` 兜底而遗漏加列
- **多租户约束调整**：改唯一约束（如 `settings.key` 全局唯一 → `(school_id, key)` 校内唯一）时，SQLite 不支持 `DROP CONSTRAINT`，需在迁移中**重建表**（新建→拷贝→删除→重命名），参考 `f1a2b3c4d5e6_settings_school_key_unique.py`；MySQL/PostgreSQL 可直接 `drop_constraint` + `create_unique_constraint`。

### 3.5 工具函数与辅助

- 公共工具统一放 `app/utils.py`：`to_dict` / `safe_filename` / `gen_student_no`（生成学号）/ `normalize_page`（分页边界规范化，所有分页列表接口须调用）。
- 权限/租户辅助统一放 `app/permissions.py`：`is_any_admin` / `is_platform_admin` / `get_teacher_class_ids` / `get_student_account`（按班级+姓名查学生账号）/ `ensure_student_access` 等，**不得**在各 router 重复实现。
- 分页参数必须调用 `normalize_page(page, page_size)`（防负数/超大 page_size），删除类接口记录不存在时统一返回 `404`。

### 3.5 文件上传

- 通用上传使用 `POST /api/uploads`，自动校验扩展名白名单和大小上限。
- 业务专用上传（如试卷）使用独立接口，格式校验更严格。
- 上传文件存储在 `backend/uploads/`，通过 `/uploads/<filename>` 访问。

### 3.6 审计日志

- 关键写操作调用 `audit(db, user, action, target, detail, class_id=None, student_id=None)` 记录。
- **学生相关操作必须传 `student_id`**（函数自动解析班级），**班级相关操作必须传 `class_id`**，用于班主任按班级查看审计日志；账号/系统级操作无需传。
- 审计日志存储在 `operation_logs` 表。
- 查看权限分级：管理员全部、班主任自己班级、科任老师不可见（由 `admin._visible_audit_class_ids` 控制）。

## 4. 前端代码规范

### 4.1 结构约定

- 页面放 `views/`，按 `student/`、`admin/` 分组；跨页复用的组件放 `components/`。
- **移动端页面放 `mobile/views/`**，布局放 `mobile/layout/`，使用 Vant 组件（`van-*`），与桌面端 Element Plus（`el-*`）互不干扰。
- API 调用统一收敛到 `api/index.js`（移动端专用接口放 `mobile/api/mobile.js`），页面**不得**直接 import axios。
- 路由统一在 `router/index.js` 注册，角色守卫统一走 `beforeEach`；移动端路由前缀 `/m`，同样纳入 `requiresTeacher` 校验。

### 4.2 组件风格

- 统一使用 `<script setup>` + Composition API。
- 使用全局 CSS 变量（`--brand`、`--text-*`、`--bg-*` 等）而非硬编码颜色。
- Element Plus 图标通过 `main.js` 全局注册，页面直接 `<el-icon><Xxx /></el-icon>`。
- 表单校验：必填字段在提交前显式校验并 `ElMessage` 提示；复杂校验建议上 `el-form` rules。

### 4.3 样式系统

- 全局样式在 `style.css` 中定义，包含 CSS 变量、组件覆盖、Markdown 渲染样式。
- 页面级样式使用 `<style scoped>`，避免污染全局。
- 通用类名：`.page-card`（卡片容器）、`.toolbar`（工具栏）、`.card-title`（卡片标题）、`.empty-state`（空状态）。

### 4.4 安全

- Markdown 渲染**必须**经过 `DOMPurify.sanitize()` 进行 XSS 过滤。
- 文件上传/下载使用 Blob 方式处理，注意 `responseType: 'blob'`。
- Token 存储在 localStorage，请求时通过 Axios 拦截器自动注入。

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

- 架构变更 → 更新 `docs/ARCHITECTURE.md`
- 开发规范变更 → 更新 `docs/DEVELOPMENT.md`
- 迭代需求 → 更新 `docs/REQUIREMENTS.md`
- 功能与快速开始 → 更新 `README.md`
- 产品规划 → 更新 `docs/PRODUCT.md`