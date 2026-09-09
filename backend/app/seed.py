"""生成演示假数据，用于本地体验与自动化测试。

用法：
    cd backend
    python -m app.seed

数据覆盖：学生档案、作业、成绩、考勤、表现（含分值）、沟通、资源、试卷、
        工作日志、评语、画像标签、周报、导入历史等。
"""

import json
import random
from datetime import date, datetime, timedelta

from faker import Faker

from app.database import Base, SessionLocal, engine
from app.models import (
    Activity,
    Assignment,
    ClassPlan,
    Classroom,
    Communication,
    Exam,
    ExcellentWork,
    ImportHistory,
    Leave,
    Performance,
    Resource,
    ReturnRecord,
    Schedule,
    School,
    Score,
    Seat,
    Setting,
    Student,
    StudentComment,
    StudentProfileTag,
    Submission,
    Talk,
    TeacherPlan,
    User,
    WeeklyReport,
    WorkComment,
    WorkLog,
)
from app.security import hash_password
from app.tenant import reset_tenant, set_tenant, tenant_scope  # noqa: F401  注册 ORM 租户隔离

fake = Faker("zh_CN")

# ========== 常量定义 ==========
SUBJECTS = [
    "C 语言程序设计", "计算机网络基础", "数据库原理",
    "网页设计与制作", "计算机组装与维护", "Python 编程基础",
]
ASSIGNMENT_SPECS = [
    ("循环结构编程练习", "使用 for/while 循环完成教材第 3 章课后习题，并截图运行结果。", "```c\n#include <stdio.h>\nint main() {\n    for (int i = 1; i <= 9; i++) {\n        for (int j = 1; j <= i; j++)\n            printf(\"%d×%d=%-2d \", j, i, i * j);\n        printf(\"\\n\");\n    }\n    return 0;\n}\n```"),
    ("数组与字符串处理", "完成数组排序和字符串查找算法，提交源码与运行截图。", "```c\nvoid bubbleSort(int arr[], int n) {\n    for (int i = 0; i < n - 1; i++)\n        for (int j = 0; j < n - i - 1; j++)\n            if (arr[j] > arr[j + 1]) {\n                int t = arr[j];\n                arr[j] = arr[j + 1];\n                arr[j + 1] = t;\n            }\n}\n```"),
    ("函数与模块化设计", "把上一章程序拆分为多个函数，说明每个函数的作用。", "```c\n// 计算平均值\nfloat average(int scores[], int n) {\n    int sum = 0;\n    for (int i = 0; i < n; i++) sum += scores[i];\n    return (float)sum / n;\n}\n```"),
    ("结构体与链表操作", "定义学生结构体并实现链表的增删改查。", "```c\ntypedef struct Student {\n    char name[20];\n    int score;\n    struct Student* next;\n} Student;\n```"),
    ("文件读写与数据统计", "实现学生成绩的读写与统计功能，输出到文件。", "```c\nFILE* fp = fopen(\"scores.txt\", \"r\");\nwhile (fscanf(fp, \"%s %d\", name, &score) != EOF) {\n    printf(\"%s: %d\\n\", name, score);\n}\n```"),
]
PERFORMANCE_POSITIVE = [
    "课堂积极回答问题，思路清晰", "主动帮助同学解决编程难题",
    "作业完成质量高，代码规范", "担任小组长，组织能力突出",
    "课后主动提问，学习态度端正", "参加技能竞赛并获奖",
    "班级值日认真负责", "课堂笔记完整，复习认真",
    "主动承担班级事务", "协助老师整理教学资料",
]
PERFORMANCE_NEGATIVE = [
    "上课玩手机，经提醒后改正", "未按时完成作业",
    "课堂打瞌睡", "迟到 10 分钟",
    "未按要求完成实验报告", "课间打闹影响他人",
    "未带课本和实验器材", "早退",
]
LEAVE_REASONS = [
    "感冒发烧", "家中有事", "参加技能竞赛", "身体不适",
    "家长来访", "就医", "参加社会实践活动", "事假",
]
COMM_METHODS = ["电话", "微信", "面谈", "家长会"]
COMM_CONTENTS = [
    "沟通近期学习情况，成绩有所进步",
    "了解学生在家表现，家长反馈积极",
    "反馈课堂纪律问题，请家长配合督促",
    "通知技能竞赛报名事宜",
    "了解学生身体状况，关注心理健康",
    "反馈期中考试成绩，分析薄弱科目",
]
RESOURCE_SPECS = [
    ("C 语言程序设计课件（第 1-5 章）", "课件"),
    ("计算机网络基础教案（全学期）", "教案"),
    ("数据库原理期末复习题", "习题"),
    ("网页设计素材包（HTML+CSS+JS）", "素材"),
    ("计算机组装与维护实验指导书", "教案"),
    ("Python 编程基础入门教程", "课件"),
    ("历年技能竞赛真题汇编", "习题"),
    ("优秀学生作品集锦", "素材"),
]
EXAM_SPECS = [
    ("C 语言程序设计 期末考试卷", "期末考试", "c_final_exam.pdf", "application/pdf", 1024000),
    ("计算机网络基础 期中测试卷", "期中测试", "network_mid.pdf", "application/pdf", 860000),
    ("数据库原理 单元测验（第 1-3 章）", "单元测验", "db_unit1.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 450000),
    ("网页设计与制作 随堂练习", "随堂练习", "web_practice.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 320000),
    ("Python 编程基础 模拟考试", "模拟考试", "python_mock.pdf", "application/pdf", 780000),
]
PLAN_TITLES = ["新学期班级工作计划", "期中班级工作总结", "期末班级工作总结"]
TEACHER_PLAN_TITLES = ["班主任个人学期计划", "班主任个人学期工作总结"]
ACTIVITY_SPECS = [
    ("班级篮球友谊赛", "为增强班级凝聚力，组织与兄弟班级的篮球友谊赛，同学们积极参与，气氛热烈。"),
    ("网络安全主题班会", "开展网络安全教育主题班会，讲解常见的网络诈骗手段和防范措施。"),
    ("计算机技能竞赛动员", "介绍本学期技能竞赛安排，鼓励同学们积极报名参加，以赛促学。"),
    ("学雷锋志愿服务活动", "组织学生到社区开展电脑维修志愿服务活动，学以致用服务社会。"),
    ("职业生涯规划讲座", "邀请优秀毕业生回校分享职业发展经验，帮助学生明确学习目标。"),
]
TAG_SPECS = [
    ("编程能手", "技能"), ("笔记达人", "学业"), ("乐于助人", "品德"),
    ("体育健将", "特长"), ("班级骨干", "品德"), ("进步之星", "学业"),
    ("技术宅", "技能"), ("文艺青年", "特长"),
]


def seed_all():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    tenant_tokens = None
    try:
        # ===== 清空旧数据 =====
        for model in (
            WeeklyReport, ImportHistory, StudentProfileTag,
            WorkComment, ExcellentWork, Submission, Assignment,
            Score, Leave, Communication, Resource, Exam, Seat,
            WorkLog, ClassPlan, TeacherPlan, Schedule, Activity, Talk, ReturnRecord,
            Performance, StudentComment, Student, Classroom, User, School, Setting,
        ):
            db.query(model).delete()
        db.commit()

        now = datetime.now()

        # ===== 学校 =====
        school = School(
            name="****学校",
            code="XYZJ01",
            address="****",
            phone="0730-8888888",
        )
        db.add(school)
        db.commit()
        # 开启租户上下文：后续新建的业务数据自动注入 school_id
        tenant_tokens = set_tenant(school.id)

        # ===== 平台超管 / 学校管理员 / 教师 =====
        # 平台超管不属于任何学校（school_id = NULL，可跨租户）
        with tenant_scope(None):
            admin = User(
                username="admin", password_hash=hash_password("admin123"),
                name="平台超管", role="super_admin",
            )
            db.add(admin)
            db.commit()
        school_admin = User(
            username="school_admin", password_hash=hash_password("admin123"),
            name="学校管理员", role="school_admin", school_id=school.id,
        )
        teacher = User(
            username="teacher", password_hash=hash_password("123456"),
            name="龙老师", role="teacher", phone="13800000001", school_id=school.id,
        )
        teacher2 = User(
            username="teacher2", password_hash=hash_password("123456"),
            name="王老师", role="teacher", phone="13800000002", school_id=school.id,
        )
        db.add_all([school_admin, teacher, teacher2])
        db.commit()
        all_teachers = [teacher, teacher2]

        # ===== 班级 =====
        class_defs = [
            ("计算机 2401 班", "J2401", "计算机应用", "一年级", teacher.id),
            ("计算机 2402 班", "J2402", "计算机应用", "一年级", teacher.id),
            ("计算机 2301 班", "J2301", "计算机网络技术", "二年级", teacher2.id),
            ("计算机 2201 班", "J2201", "计算机应用", "三年级", teacher2.id),
        ]
        classrooms = []
        for name, code, major, grade, tid in class_defs:
            c = Classroom(school_id=school.id, name=name, code=code, major=major, grade=grade, teacher_id=tid)
            db.add(c)
            classrooms.append(c)
        db.commit()

        # ===== 学生（每班 13 人，共 52 人）=====
        students = []
        student_users = []  # 对应的 User 对象
        for ci, classroom in enumerate(classrooms):
            year_map = {0: 24, 1: 24, 2: 23, 3: 22}
            year = year_map[ci]
            for j in range(13):
                student_no = f"20{year}{ci + 1:02d}{j + 1:02d}"
                name = fake.name()
                while any(s.name == name for s in students):
                    name = fake.name()
                gender = random.choice(["男", "女"])
                # 通学生约 60%，寄宿生约 40%
                student_type = "day" if random.random() < 0.6 else "boarding"
                s = Student(
                    school_id=school.id,
                    class_id=classroom.id,
                    name=name,
                    gender=gender,
                    birth_date=date(2000 + random.randint(6, 9), random.randint(1, 12), random.randint(1, 28)),
                    student_no=student_no,
                    major=classroom.major,
                    parent_name=fake.name(),
                    parent_phone=f"1{random.randint(30, 99)}{random.randint(10000000, 99999999)}",
                    student_type=student_type,
                )
                db.add(s)
                db.flush()
                students.append(s)
                u = User(
                    username=name,
                    password_hash=hash_password("123456"),
                    name=name,
                    role="student",
                    school_id=school.id,
                    class_id=classroom.id,
                )
                db.add(u)
                student_users.append(u)
        db.commit()

        # ===== 作业任务（每班 5 个）=====
        assignments = []
        for ci, classroom in enumerate(classrooms):
            creator = teacher if ci < 2 else teacher2
            for k, (title, desc, sample_code) in enumerate(ASSIGNMENT_SPECS):
                deadline_days = random.randint(3, 21)
                a = Assignment(
                    title=title,
                    description=desc,
                    content=f"# {title}\n\n{desc}\n\n## 要求\n\n1. 独立完成，代码要有注释；\n2. 提交源码与运行截图；\n3. 命名规范，注意代码风格。\n\n## 示例代码\n\n{sample_code}\n\n## 提交方式\n\n请使用 Markdown 编辑器提交，代码块使用 \\`\\`\\`c 包裹。",
                    deadline=(now + timedelta(days=deadline_days)).strftime("%Y-%m-%d %H:%M"),
                    created_by=creator.id,
                    class_id=classroom.id,
                    short_name=f"task{k + 1}",
                )
                db.add(a)
                db.flush()
                assignments.append(a)
        db.commit()

        # ===== 提交 + 优秀作品 + 评论 =====
        excellent_ids = []
        for a in assignments:
            class_students = [s for s in students if s.class_id == a.class_id]
            class_users = [u for u in student_users if u.class_id == a.class_id]
            submit_count = random.randint(7, len(class_students))
            submit_students = random.sample(class_students, submit_count)
            for s in submit_students:
                # 找到对应的 User
                user = next((u for u in class_users if u.name == s.name), None)
                if not user:
                    continue
                # 多样化提交内容
                content_templates = [
                    f"```c\n// {s.name} 的作业\n{sample_code}\n```\n\n运行结果截图见附件，代码已按要求添加注释。",
                    f"## 解题思路\n\n本次作业我采用了{random.choice(['迭代','递归','分治','贪心'])}算法解决。\n\n```c\n#include <stdio.h>\n\nint main() {{\n    // 实现代码\n    printf(\"作业完成！\\n\");\n    return 0;\n}}\n```\n\n## 运行结果\n\n程序运行正常，测试用例全部通过。",
                    f"# {a.title} 作业提交\n\n## 代码实现\n\n```c\n#include <stdio.h>\n\nint main() {{\n    printf(\"{s.name} 的作业提交\\n\");\n    return 0;\n}}\n```\n\n## 遇到的问题\n\n在实现过程中遇到了{random.choice(['指针使用','内存管理','类型转换','循环嵌套'])}的问题，通过查阅资料已解决。",
                ]
                content = random.choice(content_templates)
                has_file = random.random() < 0.3
                sub = Submission(
                    assignment_id=a.id,
                    student_id=user.id,
                    content=content,
                    filename=f"{s.name}_作业_{a.short_name}.zip" if has_file else None,
                    filepath=f"uploads/demo_{a.short_name}_{s.student_no}.zip" if has_file else None,
                )
                db.add(sub)
                db.flush()
                if random.random() < 0.25:
                    note = random.choice([
                        "代码规范，思路清晰，值得大家学习。",
                        "注释详细，逻辑严谨，优秀作品！",
                        "解法独特，代码简洁高效。",
                        "结构清晰，运行结果正确，继续保持。",
                    ])
                    e = ExcellentWork(submission_id=sub.id, selected_by=a.created_by, note=note)
                    db.add(e)
                    db.flush()
                    excellent_ids.append(e.id)
        db.commit()

        # 评论
        all_users = [admin, teacher, teacher2] + student_users
        for eid in excellent_ids[:30]:
            for _ in range(random.randint(1, 3)):
                commenter = random.choice(all_users)
                db.add(WorkComment(
                    excellent_id=eid,
                    user_id=commenter.id,
                    content=random.choice([
                        "思路很清晰，学到了！", "注释写得很详细，赞一个",
                        "这个解法很巧妙", "我也试了同样的方法，感谢分享",
                        "代码风格很规范，向你学习", "运行效率很高，有什么优化技巧吗？",
                        "很棒的作品！", "看了你的代码，我有了新的思路",
                    ]),
                ))
        db.commit()

        # ===== 成绩（每生 2-4 次考试，含不同考试类型，时间分散在近 90 天）=====
        exam_types = ["期中考试", "期末考试", "单元测验", "随堂测验"]
        for s in students:
            subjects = random.sample(SUBJECTS, random.randint(2, len(SUBJECTS)))
            for subject in subjects:
                for _ in range(random.randint(1, 2)):
                    score = max(30, min(100, round(random.gauss(72, 15), 1)))
                    days_ago = random.randint(1, 90)
                    exam_date = now - timedelta(days=days_ago)
                    db.add(Score(
                        student_id=s.id,
                        subject=subject,
                        score=score,
                        exam_name=random.choice(exam_types),
                        created_at=exam_date,
                    ))
        db.commit()

        # ===== 考勤请假（含近 7 天趋势数据）=====
        for s in students:
            if random.random() < 0.5:
                days_ago = random.randint(1, 30)
                leave_date = now - timedelta(days=days_ago)
                db.add(Leave(
                    student_id=s.id,
                    reason=random.choice(LEAVE_REASONS),
                    start_date=leave_date.date(),
                    end_date=(leave_date + timedelta(days=random.randint(0, 2))).date(),
                    status=random.choice(["登记", "已销假"]),
                    created_at=leave_date,
                ))
        # 近 7 天每日请假（确保看板折线图有数据）
        for day_offset in range(7):
            day = now - timedelta(days=day_offset)
            day_str = day.date()
            count = random.randint(0, 3)
            for _ in range(count):
                s = random.choice(students)
                db.add(Leave(
                    student_id=s.id,
                    reason=random.choice(LEAVE_REASONS[:4]),
                    start_date=day_str,
                    end_date=day_str,
                    status="登记",
                    created_at=day,
                ))
        db.commit()

        # ===== 表现记录（含分值；积分管理已合并入表现管理）=====
        pf_total = 0
        for s in students:
            for _ in range(random.randint(2, 6)):
                is_positive = random.random() < 0.65
                ptype = "积极" if is_positive else "消极"
                content = random.choice(PERFORMANCE_POSITIVE if is_positive else PERFORMANCE_NEGATIVE)
                points = random.choice([1, 2, 3, 5]) if is_positive else random.choice([-1, -2, -3])
                db.add(Performance(
                    student_id=s.id,
                    ptype=ptype,
                    content=content,
                    points=points,
                    created_at=now - timedelta(days=random.randint(1, 60)),
                ))
                pf_total += 1
        db.commit()

        # ===== 家校沟通 =====
        for s in students:
            if random.random() < 0.35:
                db.add(Communication(
                    student_id=s.id,
                    method=random.choice(COMM_METHODS),
                    content=random.choice(COMM_CONTENTS),
                    feedback=random.choice([
                        "家长表示会配合学校工作",
                        "家长感谢老师的关心",
                        "家长反馈学生在家表现良好",
                        "家长希望加强家校沟通",
                    ]),
                ))
        db.commit()

        # ===== 资源 =====
        for name, category in RESOURCE_SPECS:
            db.add(Resource(
                name=name,
                category=category,
                filename=f"{name}.pdf",
                filepath=f"uploads/resource_{random.randint(1, 9999):04d}.pdf",
            ))
        db.commit()

        # ===== 试卷（文件型）=====
        for title, exam_type, filename, mime_type, size in EXAM_SPECS:
            db.add(Exam(
                title=title,
                exam_type=exam_type,
                filename=filename,
                filepath=f"uploads/exam_{random.randint(1, 9999):04d}{filename[filename.rfind('.'):]}",
                filesize=size,
                filetype=filename[filename.rfind('.'):],
            ))
        db.commit()

        # ===== 座位表 =====
        for classroom in classrooms[:2]:
            class_students = [s for s in students if s.class_id == classroom.id]
            layout = [class_students[i:i + 6] for i in range(0, len(class_students), 6)]
            db.add(Seat(
                class_id=classroom.id,
                layout=json.dumps([[s.id for s in row] for row in layout], ensure_ascii=False),
                columns=6,
            ))
        db.commit()

        # ===== 工作日志（30 天）=====
        for i in range(30):
            day = now - timedelta(days=i)
            db.add(WorkLog(
                teacher_id=teacher.id if i < 20 else teacher2.id,
                date=day.date(),
                content=f"## 今日工作\n\n- 批改作业（{random.randint(8, 15)} 份）\n- 与 {random.randint(1, 3)} 名学生谈心\n- 备课：{random.choice(SUBJECTS)}\n\n## 班级情况\n\n- 出勤：正常\n- 卫生：{random.choice(['良好','优秀','合格'])}\n\n## 明日计划\n\n- 检查班级卫生\n- {random.choice(['组织主题班会','批改单元测验','准备技能竞赛','整理班级档案'])}",
            ))
        db.commit()

        # ===== 计划总结 =====
        for title in PLAN_TITLES:
            db.add(ClassPlan(
                teacher_id=teacher.id,
                title=title,
                plan_type="计划" if "计划" in title else "总结",
                content="## 一、指导思想\n\n以培养学生职业技能为核心，全面提升学生综合素质。\n\n## 二、工作目标\n\n1. 班级学风建设\n2. 技能竞赛参与率\n3. 学生心理健康\n\n## 三、具体措施\n\n1. 每周一次技能训练\n2. 每月一次主题班会\n3. 定期家校沟通\n\n## 四、时间安排\n\n详见附表",
            ))
        for title in TEACHER_PLAN_TITLES:
            db.add(TeacherPlan(
                teacher_id=teacher.id,
                title=title,
                plan_type="计划" if "计划" in title else "总结",
                content="本学期工作重点：抓学风、促养成、强技能。重点关注学生编程能力和职业素养的培养。",
            ))
        db.commit()

        # ===== 课程表 =====
        for classroom in classrooms[:2]:
            for day in range(1, 6):
                for period in range(1, 7):
                    db.add(Schedule(
                        class_id=classroom.id,
                        day_of_week=day,
                        period=period,
                        subject=random.choice(SUBJECTS),
                        teacher_name=random.choice([teacher.name, teacher2.name]),
                    ))
        db.commit()

        # ===== 班级活动 =====
        for title, content in ACTIVITY_SPECS:
            db.add(Activity(
                class_id=random.choice(classrooms).id,
                title=title,
                content=content,
            ))
        db.commit()

        # ===== 谈心 =====
        for s in random.sample(students, min(20, len(students))):
            db.add(Talk(
                student_id=s.id,
                teacher_id=random.choice(all_teachers).id,
                content=f"与 {s.name} 谈心，了解近期{random.choice(['学习','生活','心理','家庭'])}状态。{random.choice(['学生态度积极，沟通顺畅','需要持续关注','建议家长配合督促','已制定改进计划'])}。",
            ))
        db.commit()

        # ===== 返校记录 =====
        for s in random.sample(students, min(12, len(students))):
            days_ago = random.randint(1, 30)
            db.add(ReturnRecord(
                student_id=s.id,
                return_date=(now - timedelta(days=days_ago)).date(),
                reason=random.choice(["周末返校", "假期返校", "实习返校"]),
                note=random.choice(["正常", "按时到校", "略有延迟"]),
            ))
        db.commit()

        # ===== 学生评语 =====
        comment_templates = [
            "{} 同学学习认真，态度端正，希望能继续保持并更上一层楼。",
            "{} 同学专业技能突出，在班级中起到了良好的带头作用，建议多参加技能竞赛。",
            "{} 同学本学期进步明显，作业完成质量和课堂参与度都有显著提升。",
            "{} 同学性格开朗，团结同学，但在学习主动性上还有提升空间。",
            "{} 同学编程能力强，但需要加强理论知识的学习，做到理论与实践并重。",
        ]
        for s in random.sample(students, min(20, len(students))):
            db.add(StudentComment(
                student_id=s.id,
                content=random.choice(comment_templates).format(s.name),
            ))
        db.commit()

        # ===== 画像标签 =====
        for s in random.sample(students, min(30, len(students))):
            tags = random.sample(TAG_SPECS, random.randint(1, 3))
            for tag, category in tags:
                db.add(StudentProfileTag(
                    student_id=s.id,
                    tag=tag,
                    category=category,
                ))
        db.commit()

        # ===== 导入历史 =====
        import_types = ["student", "score"]
        for _ in range(5):
            itype = random.choice(import_types)
            total = random.randint(20, 50)
            success = random.randint(15, total)
            errors = []
            if success < total:
                for i in range(total - success):
                    errors.append(f"第{random.randint(2, total + 1)}行：{random.choice(['学号重复','班级不存在','必填字段为空','成绩格式错误'])}")
            db.add(ImportHistory(
                import_type=itype,
                filename=f"{'学生' if itype == 'student' else '成绩'}导入_{random.randint(1, 99):02d}.xlsx",
                total_rows=total,
                success_rows=success,
                error_rows=total - success,
                errors=json.dumps(errors[:20], ensure_ascii=False) if errors else None,
                user_id=teacher.id,
            ))
        db.commit()

        # ===== 周报 =====
        for classroom in classrooms[:2]:
            for week_offset in range(3):
                week_start = (now - timedelta(days=7 * (week_offset + 1))).date()
                week_end = (now - timedelta(days=7 * week_offset)).date()
                class_students = [s for s in students if s.class_id == classroom.id]
                top_names = ", ".join(random.sample([s.name for s in class_students], min(3, len(class_students))))
                content = f"""# {classroom.name} 班级周报

> 周期：{week_start} ~ {week_end} ｜ 班级人数：{len(class_students)} 人

## 一、本周概况

- **出勤率**：{random.randint(92, 100)}%
- **请假人次**：{random.randint(0, 5)} 人次
- **积极表现**：{random.randint(5, 20)} 次
- **消极表现**：{random.randint(0, 5)} 次

## 二、积分排行

1. {top_names}

## 三、本周总结

本周班级整体表现{random.choice(['良好','优秀','正常'])}，同学们在{random.choice(SUBJECTS)}课程中表现积极。

## 四、下周计划

- 组织{random.choice(['主题班会','技能训练','模拟考试'])}
- 重点关注{random.choice(['作业完成情况','课堂纪律','技能竞赛准备'])}"""
                db.add(WeeklyReport(
                    class_id=classroom.id,
                    title=f"{classroom.name} 第{week_offset + 1}周周报",
                    week_start=week_start,
                    week_end=week_end,
                    content=content,
                    data_snapshot=json.dumps({"attendance": random.randint(92, 100), "positive": random.randint(5, 20)}, ensure_ascii=False),
                    created_by=teacher.id if classroom.teacher_id == teacher.id else teacher2.id,
                ))
        db.commit()

        # ===== 系统设置 =====
        db.add_all([
            Setting(key="grade", value="一年级"),
            Setting(key="school_name", value=school.name),
            Setting(key="semester", value="2025-2026 学年第一学期"),
            Setting(key="max_upload_size", value="20971520"),
        ])
        db.commit()

        # ===== 统计输出 =====
        print("=" * 50)
        print("  TeachHub 测试数据生成完成")
        print("=" * 50)
        print(f"  学校：{school.name}")
        print(f"  班级：{len(classrooms)} 个")
        print(f"  学生：{len(students)} 名（含通学生 {sum(1 for s in students if s.student_type == 'day')} + 寄宿生 {sum(1 for s in students if s.student_type == 'boarding')}）")
        print(f"  作业：{len(assignments)} 个任务")
        print(f"  成绩：{db.query(Score).count()} 条")
        print(f"  请假：{db.query(Leave).count()} 条")
        print(f"  表现：{pf_total} 条（含分值字段）")
        print(f"  沟通：{db.query(Communication).count()} 条")
        print(f"  资源：{db.query(Resource).count()} 个")
        print(f"  试卷：{db.query(Exam).count()} 份")
        print(f"  日志：{db.query(WorkLog).count()} 篇")
        print(f"  画像标签：{db.query(StudentProfileTag).count()} 个")
        print(f"  周报：{db.query(WeeklyReport).count()} 份")
        print(f"  导入历史：{db.query(ImportHistory).count()} 条")

        # ===== 第二所学校（用于验证跨租户数据隔离）=====
        school2 = School(
            name="第二职业技术学校", code="DEZX01",
            address="示例地址", phone="0730-7777777",
        )
        db.add(school2)
        db.commit()
        with tenant_scope(school2.id):
            t3 = User(
                username="teacher3", password_hash=hash_password("123456"),
                name="李老师", role="teacher", phone="13800000003", school_id=school2.id,
            )
            db.add(t3)
            db.commit()
            c3 = Classroom(
                school_id=school2.id, name="机电 2401 班", code="JD2401",
                major="机电技术应用", grade="一年级", teacher_id=t3.id,
            )
            db.add(c3)
            db.commit()
            for i in range(1, 6):
                nm = f"二校学生{i}"
                st = Student(
                    school_id=school2.id, class_id=c3.id, name=nm, gender="男",
                    student_no=f"DEZX{i:04d}", major="机电技术应用", student_type="day",
                )
                db.add(st)
                db.flush()
                db.add(User(
                    username=nm, password_hash=hash_password("123456"), name=nm,
                    role="student", school_id=school2.id, class_id=c3.id,
                ))
                if i <= 2:
                    db.add(Score(
                        school_id=school2.id, student_id=st.id,
                        subject="机械制图", score=80 + i,
                    ))
            db.commit()
        print(f"  第二所学校：{school2.name}（班级 1 个 / 学生 5 名，用于验证隔离）")
        print()
        print("  平台超管：admin / admin123（跨学校）")
        print("  学校管理员：school_admin / admin123（仅本校）")
        print("  教师账号：teacher / 123456、teacher2 / 123456（默认校）、teacher3 / 123456（第二校）")
        print("  学生账号：学校 + 班级 + 姓名 / 123456")
        print("=" * 50)
    finally:
        if tenant_tokens is not None:
            reset_tenant(tenant_tokens)
        db.close()


if __name__ == "__main__":
    seed_all()