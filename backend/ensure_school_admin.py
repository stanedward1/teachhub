"""幂等补齐多租户默认角色：为默认租户创建学校管理员账号（若不存在）。

用法：python ensure_school_admin.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal  # noqa: E402
from app.models import School, User  # noqa: E402
from app.security import hash_password  # noqa: E402


def main():
    db = SessionLocal()
    try:
        school = db.query(School).order_by(School.id).first()
        if school is None:
            print("无学校记录，请先运行 seed")
            return

        existing = db.query(User).filter(
            User.school_id == school.id, User.username == "school_admin"
        ).first()
        if existing:
            print(f"学校管理员已存在：{existing.username}（school_id={school.id}）")
            return

        admin = User(
            username="school_admin",
            password_hash=hash_password("admin123"),
            name="学校管理员",
            role="school_admin",
            school_id=school.id,
        )
        db.add(admin)
        db.commit()
        print(f"已创建学校管理员：school_admin / admin123（学校「{school.name}」，id={school.id}）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
