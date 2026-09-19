"""F3 刷新令牌（refresh token）接口测试。

保护前端「401 静默刷新 + 登出撤销」所依赖的后端契约：

- 登录签发 access + refresh 双令牌；
- `/api/auth/refresh` 一次性轮换：签发新令牌对，旧刷新令牌立即失效；
- `/api/auth/logout` 撤销刷新令牌，且**幂等**（重复登出/未知令牌均返回成功）；
- 非法 / 已撤销令牌一律 401。

这些用例同时是「前端登出已接线」的回归防线：一旦后端撤销语义被改坏，
前端即使正确调用了 `/api/auth/logout`，令牌也不会真正失效。
"""


def _login(client, username="teacher", password="123456"):
    """登录并返回响应体（含 token / refresh_token）。"""
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()


def test_login_returns_refresh_token(client):
    """登录必须同时返回 access token 与 refresh token，且两者不同。"""
    data = _login(client)
    assert data["token"]
    assert data["refresh_token"]
    assert data["refresh_token"] != data["token"]
    assert data["user"]["role"] == "teacher"


def test_refresh_rotates_and_invalidates_old_token(client):
    """刷新为一次性轮换：返回新令牌对，旧刷新令牌重放必须 401。"""
    old_rt = _login(client)["refresh_token"]

    first = client.post("/api/auth/refresh", json={"refresh_token": old_rt})
    assert first.status_code == 200
    rotated = first.json()
    assert rotated["token"]
    assert rotated["refresh_token"]
    assert rotated["refresh_token"] != old_rt  # 确实轮换出了新令牌
    assert rotated["token_type"] == "bearer"

    # 旧刷新令牌已被撤销 → 重放 401
    replay = client.post("/api/auth/refresh", json={"refresh_token": old_rt})
    assert replay.status_code == 401

    # 新刷新令牌可用
    again = client.post("/api/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert again.status_code == 200


def test_logout_revokes_refresh_token(client):
    """登出后该刷新令牌不可再用于换取新令牌（前端登出接线所依赖的核心语义）。"""
    rt = _login(client)["refresh_token"]

    out = client.post("/api/auth/logout", json={"refresh_token": rt})
    assert out.status_code == 200
    assert out.json() == {"ok": True}

    # 撤销生效：刷新失败
    resp = client.post("/api/auth/refresh", json={"refresh_token": rt})
    assert resp.status_code == 401


def test_logout_is_idempotent(client):
    """重复登出、以及撤销未知令牌都必须返回成功（前端可能重试/重复点击）。"""
    rt = _login(client)["refresh_token"]
    assert client.post("/api/auth/logout", json={"refresh_token": rt}).status_code == 200
    # 第二次登出同一令牌
    assert client.post("/api/auth/logout", json={"refresh_token": rt}).status_code == 200
    # 完全未知的令牌
    assert client.post("/api/auth/logout", json={"refresh_token": "bogus"}).status_code == 200


def test_refresh_with_invalid_token_returns_401(client):
    """非法刷新令牌统一 401（并带中文提示，供前端识别为会话过期）。"""
    resp = client.post("/api/auth/refresh", json={"refresh_token": "definitely-not-valid"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "登录已过期，请重新登录"


def test_logout_does_not_affect_other_sessions(client):
    """撤销一个会话不应影响另一个会话的刷新令牌（多设备登录互不干扰）。"""
    rt_a = _login(client)["refresh_token"]
    rt_b = _login(client)["refresh_token"]
    assert rt_a != rt_b

    assert client.post("/api/auth/logout", json={"refresh_token": rt_a}).status_code == 200

    assert client.post("/api/auth/refresh", json={"refresh_token": rt_a}).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": rt_b}).status_code == 200
