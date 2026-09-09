"""TeachHub 后端 API 自动化测试。

运行：
    cd backend
    python -m pytest tests/ -v
"""

from app.database import SessionLocal
from app.models import Assignment, Classroom, User


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------- 认证 ----------------
def test_teacher_login(client, teacher_token):
    assert teacher_token


def test_student_login(client, student_token):
    assert student_token


def test_wrong_password(client):
    resp = client.post("/api/auth/login", json={"username": "teacher", "password": "wrong"})
    assert resp.status_code == 401


def test_register_student(client):
    resp = client.post(
        "/api/auth/register",
        json={"name": "新同学", "password": "123456", "class_id": 1},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "student"


# ---------------- 权限隔离 ----------------
def test_student_can_list_assignments(client, student_token):
    resp = client.get("/api/homework/assignments", headers=auth(student_token))
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_student_cannot_access_admin(client, student_token):
    resp = client.get("/api/students", headers=auth(student_token))
    assert resp.status_code == 403


def test_student_cannot_create_assignment(client, student_token):
    resp = client.post(
        "/api/homework/assignments",
        json={"title": "x", "content": "y", "class_id": 1},
        headers=auth(student_token),
    )
    assert resp.status_code == 403


def test_teacher_can_access_admin(client, teacher_token):
    resp = client.get("/api/students", headers=auth(teacher_token))
    assert resp.status_code == 200
    assert "total" in resp.json()


def test_teacher_can_access_dashboard(client, teacher_token):
    resp = client.get("/api/stats/dashboard", headers=auth(teacher_token))
    assert resp.status_code == 200
    assert "counts" in resp.json()


# ---------------- 作业流程 ----------------
def test_student_can_submit_and_view(client, student_token):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username != "admin").filter(User.role == "student").first()
        # 找到该学生班级下的一个作业
        assignment = db.query(Assignment).filter(Assignment.class_id == user.class_id).first()
        assignment_id = assignment.id
    finally:
        db.close()

    resp = client.post(
        f"/api/homework/assignments/{assignment_id}/submissions",
        json={"content": "这是我的作业提交内容"},
        headers=auth(student_token),
    )
    assert resp.status_code == 200

    resp = client.get(
        f"/api/homework/assignments/{assignment_id}/submissions",
        headers=auth(student_token),
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_student_cannot_submit_other_class(client):
    db = SessionLocal()
    try:
        class_ids = [c.id for c in db.query(Classroom).all()]
        assert len(class_ids) >= 2
        user = db.query(User).filter(User.role == "student", User.class_id == class_ids[0]).first()
        assignment = db.query(Assignment).filter(Assignment.class_id == class_ids[1]).first()
    finally:
        db.close()

    resp = client.post(
        "/api/auth/login",
        json={"username": user.name, "class_id": user.class_id, "password": "123456"},
    )
    token = resp.json()["token"]
    resp = client.post(
        f"/api/homework/assignments/{assignment.id}/submissions",
        json={"content": "越权提交"},
        headers=auth(token),
    )
    assert resp.status_code == 403


# ---------------- 教师工作台 CRUD ----------------
def test_student_crud(client, teacher_token):
    # 教师须在自己负责的班级添加学生
    resp = client.post(
        "/api/students",
        json={"name": "测试学生", "student_no": "T999", "gender": "男", "class_id": 1},
        headers=auth(teacher_token),
    )
    assert resp.status_code == 200
    sid = resp.json()["id"]

    resp = client.put(
        f"/api/students/{sid}",
        json={"name": "测试学生改"},
        headers=auth(teacher_token),
    )
    assert resp.json()["name"] == "测试学生改"

    resp = client.delete(f"/api/students/{sid}", headers=auth(teacher_token))
    assert resp.status_code == 200


def test_score_crud(client, teacher_token):
    resp = client.post(
        "/api/scores",
        json={"student_id": 1, "subject": "C 语言", "score": 88},
        headers=auth(teacher_token),
    )
    assert resp.status_code == 200
    resp = client.get("/api/scores", headers=auth(teacher_token))
    assert resp.json()["total"] >= 1


def test_worklog_crud(client, teacher_token):
    resp = client.post(
        "/api/work-logs",
        json={"date": "2025-01-01", "content": "测试日志"},
        headers=auth(teacher_token),
    )
    assert resp.status_code == 200


# ---------------- 优秀作品与评论 ----------------
def test_excellent_flow(client, teacher_token):
    resp = client.get("/api/homework/excellent", headers=auth(teacher_token))
    assert resp.status_code == 200
    items = resp.json()["items"]
    if items:
        eid = items[0]["id"]
        resp = client.post(
            f"/api/homework/excellent/{eid}/comments",
            json={"content": "很棒的作品"},
            headers=auth(teacher_token),
        )
        assert resp.status_code == 200
