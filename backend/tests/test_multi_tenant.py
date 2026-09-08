"""多租户数据隔离与角色权限测试。

依赖 conftest 的 seed_all() 生成：默认租户（学校 1）+ 第二所学校（学校 2），
以及 super_admin / school_admin / teacher / teacher3 等账号。
"""
from app.database import SessionLocal
from app.models import Classroom, Student, User


def _login(client, username, password, school_id=None):
    body = {"username": username, "password": password}
    if school_id:
        body["school_id"] = school_id
    return client.post("/api/auth/login", json=body)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _get_school2_student_id():
    """第二所学校（学校 2）的一名学生 id。"""
    db = SessionLocal()
    try:
        s = db.query(Student).filter(Student.school_id == 2).first()
        return s.id if s else None
    finally:
        db.close()


# ---------------- 登录与租户上下文 ----------------
def test_role_login(client):
    # 平台超管：不传学校，school_id 为 None
    r = _login(client, "admin", "admin123")
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "super_admin"
    assert r.json()["user"]["school_id"] is None

    # 学校管理员：传学校 1
    r = _login(client, "school_admin", "admin123", school_id=1)
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "school_admin"
    assert r.json()["user"]["school_id"] == 1

    # 第二校教师
    r = _login(client, "teacher3", "123456", school_id=2)
    assert r.status_code == 200


def test_student_login_requires_school(client):
    # 学生登录带学校 + 班级
    r = _login(client, "二校学生1", "123456", school_id=2)
    # 学生登录还需 class_id，缺 class_id 走教师/管理员分支，这里应定位不到 -> 401
    assert r.status_code in (400, 401, 409)


# ---------------- 数据可见范围（隔离核心） ----------------
def test_school_list_scope(client):
    admin_token = _login(client, "admin", "admin123").json()["token"]
    sa_token = _login(client, "school_admin", "admin123", 1).json()["token"]

    r = client.get("/api/schools", headers=_auth(admin_token))
    assert r.json()["total"] == 2  # 平台超管看全部

    r = client.get("/api/schools", headers=_auth(sa_token))
    assert r.json()["total"] == 1  # 学校管理员只看本校


def test_student_list_scope(client):
    admin_token = _login(client, "admin", "admin123").json()["token"]
    sa_token = _login(client, "school_admin", "admin123", 1).json()["token"]
    t3_token = _login(client, "teacher3", "123456", 2).json()["token"]

    admin = client.get("/api/students?page_size=500", headers=_auth(admin_token)).json()
    sa = client.get("/api/students?page_size=500", headers=_auth(sa_token)).json()
    t3 = client.get("/api/students?page_size=500", headers=_auth(t3_token)).json()

    # 平台超管 >= 本校管理员 > 第二校教师（数据范围逐级收敛）
    assert admin["total"] >= sa["total"]
    assert sa["total"] > t3["total"]

    # 隔离：本校管理员与第二校教师的学生集合无交集
    sa_ids = {s["id"] for s in sa["items"]}
    t3_ids = {s["id"] for s in t3["items"]}
    assert not (sa_ids & t3_ids)

    # 第二校教师只能看到本校（school_id=2）的学生
    assert t3["total"] > 0
    assert all(s.get("school_id") == 2 for s in t3["items"])


# ---------------- 越权拦截（跨校按 ID 访问 -> 404） ----------------
def test_cross_school_access_blocked(client):
    sid = _get_school2_student_id()
    assert sid is not None

    sa_token = _login(client, "school_admin", "admin123", 1).json()["token"]
    t1_token = _login(client, "teacher", "123456", 1).json()["token"]

    # 学校管理员 / 教师访问第二校学生 -> 404（不泄露存在性）
    r = client.put(f"/api/students/{sid}", json={"name": "越权改名"}, headers=_auth(sa_token))
    assert r.status_code == 404
    r = client.put(f"/api/students/{sid}", json={"name": "越权改名"}, headers=_auth(t1_token))
    assert r.status_code == 404


# ---------------- 平台超管专属能力 ----------------
def test_platform_overview_permission(client):
    admin_token = _login(client, "admin", "admin123").json()["token"]
    sa_token = _login(client, "school_admin", "admin123", 1).json()["token"]

    r = client.get("/api/admin/platform/overview", headers=_auth(admin_token))
    assert r.status_code == 200
    assert r.json()["school_count"] == 2

    r = client.get("/api/admin/platform/overview", headers=_auth(sa_token))
    assert r.status_code == 403


def test_school_create_only_platform_admin(client):
    admin_token = _login(client, "admin", "admin123").json()["token"]
    sa_token = _login(client, "school_admin", "admin123", 1).json()["token"]

    r = client.post("/api/schools", json={"name": "越权建校", "code": "YQ01"}, headers=_auth(sa_token))
    assert r.status_code == 403

    r = client.post(
        "/api/schools",
        json={"name": "测试新校", "code": "TST01", "admin_username": "tadmin", "admin_password": "School@123"},
        headers=_auth(admin_token),
    )
    assert r.status_code == 200
    # 新学校管理员可登录
    r = _login(client, "tadmin", "School@123", school_id=r.json()["id"])
    assert r.status_code == 200


# ---------------- 停用学校拦截 ----------------
def test_disabled_school_blocked(client):
    admin_token = _login(client, "admin", "admin123").json()["token"]

    # 停用第二校
    r = client.put("/api/schools/2/status", json={"status": "disabled"}, headers=_auth(admin_token))
    assert r.status_code == 200

    # 第二校教师登录应被拒绝
    r = _login(client, "teacher3", "123456", school_id=2)
    assert r.status_code == 403

    # 恢复
    client.put("/api/schools/2/status", json={"status": "active"}, headers=_auth(admin_token))
