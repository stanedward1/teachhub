"""教师工作台业务服务层（Service Layer）。

与 `app/routers/workbench/` 的资源域一一对应，承载原子路由中的业务逻辑与数据访问。

分层约定（B1 重构）：
- **router**（`app/routers/workbench/*`）只负责：`@router` 路径声明 / 依赖注入 / 参数解析 /
  调用 service / 返回。
- **service**（本包）承载业务逻辑与 SQLAlchemy 数据访问，函数首参为 `db: Session`，
  可抛 `HTTPException` 以保持与重构前完全一致的错误语义（状态码 + 中文文案）。

约束：
- 对外 API 路径、请求/响应字段、状态码、中文提示文案、`audit(...)` 文案与调用时机
  必须与重构前**完全一致**。
- service 不得 import router，避免循环依赖；共享依赖与辅助统一放在 `_common.py`。
"""
