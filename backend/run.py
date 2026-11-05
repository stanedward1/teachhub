import os

import uvicorn

if __name__ == "__main__":
    # ENV=production 时关闭自动重载：reload 会让 uvicorn 起一个 watchfiles 监听整个工程目录，
    # 在服务器上白吃 CPU，且每个请求多一层 reloader 转发；本地开发保持原有热更新行为。
    _env = os.getenv("ENV", "development").strip().lower()
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=_env != "production")
