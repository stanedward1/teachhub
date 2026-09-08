"""修复历史数据：为「有登录账号但无学生档案」的学生补建 students 记录。

可重复执行。用法：python repair_student_profiles.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal  # noqa: E402
from app.models import Classroom, Student, User  # noqa: E402
from app.utils import gen_student_no  # noqa: E402


def main():
    db = SessionLocal()
    try:
        fixed_profile, fixed_school = [], []
        users = db.query(User).filter(User.role == "student").all()
        for u in users:
            cls = db.get(Classroom, u.class_id) if u.class_id else None
            # 账号缺少租户归属时，按班级所属学校补齐
            if u.school_id is None and cls and cls.school_id:
                u.school_id = cls.school_id
                fixed_school.append((u.id, u.name, cls.school_id))
            if not u.class_id:
                continue
            stu = (
                db.query(Student)
                .filter(Student.class_id == u.class_id, Student.name == u.name)
                .first()
            )
            if stu:
                continue
            db.add(
                Student(
                    school_id=cls.school_id if cls else u.school_id,
                    class_id=u.class_id,
                    name=u.name,
                    student_no=gen_student_no(db, Student),
                    gender="男",
                    student_type="day",
                    status="active",
                )
            )
            fixed_profile.append((u.id, u.name, u.class_id))
        db.commit()
        print(f"补建学生档案 {len(fixed_profile)} 条: {fixed_profile}")
        print(f"补填学校归属 {len(fixed_school)} 条: {fixed_school}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
