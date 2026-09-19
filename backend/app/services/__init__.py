"""业务服务层（Service Layer）。

分层约定（B1 重构）：

- **router**（`app/routers/**`）只负责：声明 `@router` 路径 / 依赖注入 / 参数解析 / 调用 service / 返回。
- **service**（`app/services/**`）承载业务逻辑与数据访问（SQLAlchemy Session），
  可抛 `HTTPException` 以保持与重构前完全一致的错误语义（状态码 + 中文文案）。
- 每个域一个模块：`<domain>_service.py`；子域较多时按目录组织（如 `services/workbench/`）。

约束：
- 对外 API 路径、请求/响应字段、状态码、中文提示文案、刷新时机必须与重构前**完全一致**。
- 服务函数统一以 `db: Session` 作为第一个参数，保持无全局状态、可单测。
- 租户隔离由 `app/tenant.py` 的 ORM 事件自动完成，service 内**不要**手动拼 `school_id` 过滤
  （除非接口层需要显式双保险，参见 `tenant.tenant_filtered_query`）。
"""
