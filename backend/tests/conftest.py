import os
import tempfile

# 必须在导入 app 之前设置数据库环境变量
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_all  # noqa: E402

# 测试环境关闭限流：用例会反复调用 /api/auth/login，触发 @limiter.limit("5/minute")
# 的 429（跨用例累计）。仅禁用测试进程内的 Limiter.enabled，生产限流不变
# （main.py 仍挂载 app.state.limiter，登录 5/min、注册 10/min、刷新 30/min 照常生效）。
app.state.limiter.enabled = False


@pytest.fixture(scope="session", autouse=True)
def init_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_all()
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def student_token(client):
    from app.database import SessionLocal
    from app.models import Classroom, User

    db = SessionLocal()
    try:
        cls = db.query(Classroom).first()
        user = db.query(User).filter(User.role == "student", User.class_id == cls.id).first()
        name = user.name
        class_id = user.class_id
    finally:
        db.close()
    resp = client.post(
        "/api/auth/login",
        json={"username": name, "class_id": class_id, "password": "123456"},
    )
    assert resp.status_code == 200
    return resp.json()["token"]


@pytest.fixture()
def teacher_token(client):
    resp = client.post("/api/auth/login", json={"username": "teacher", "password": "123456"})
    assert resp.status_code == 200
    return resp.json()["token"]
