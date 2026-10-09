"""公共元数据业务逻辑（B1 分层：自 routers/meta.py 下沉，行为完全不变）。"""
from sqlalchemy.orm import Session

from app.models import Classroom

PRACTICE_DATA = {
    "oj": [
        {"name": "洛谷", "url": "https://www.luogu.com.cn", "desc": "国内最大的 OJ，题目分级清晰，新手友好"},
        {"name": "PTA", "url": "https://pintia.cn", "desc": "浙大出品，配套课程题库，适合随堂练习"},
        {"name": "牛客网", "url": "https://www.nowcoder.com", "desc": "算法竞赛与面试题，社区活跃"},
        {"name": "力扣 LeetCode", "url": "https://leetcode.cn", "desc": "算法入门到进阶，题解丰富"},
        {"name": "Codeforces", "url": "https://codeforces.com", "desc": "国际知名算法竞赛平台"},
    ],
    "tutorials": [
        {"name": "C 语言入门教程", "url": "https://www.runoob.com/cprogramming/c-tutorial.html", "desc": "零基础 C 语言图文教程"},
        {"name": "C 语言中文网", "url": "https://c.biancheng.net", "desc": "系统全面的 C 语言学习站"},
        {"name": "翁恺 C 语言课程", "url": "https://www.icourse163.org", "desc": "浙大翁恺老师的经典 C 语言 MOOC"},
        {"name": "C Primer Plus 习题", "url": "https://github.com", "desc": "经典教材配套练习"},
    ],
}


def class_options(db: Session, school_id: int | None = None) -> dict:
    """班级下拉选项（登录/注册时使用，无需登录）。仅返回未毕业班级。

    传入 school_id 时只返回该校班级（多租户下学生登录页按学校级联）。

    🔴 未传 school_id 时**返回空列表**：本端点无需登录，若不加限制，匿名请求即可拿到
    **全部学校**的班级名称/代码/专业（跨租户信息泄露）。此前无 school_id 时只是跳过
    过滤条件，等于把多租户隔离交给调用方自觉 —— 已收紧为「无 school_id 即空」。
    登录页/注册页必须先选定学校（school_id）才能看到班级。
    """
    if not school_id:
        return {"items": []}
    q = (
        db.query(Classroom)
        .filter(Classroom.is_graduated.is_(False))
        .filter(Classroom.school_id == school_id)
    )
    rows = q.order_by(Classroom.id).all()
    # 同时返回 code：班级代码常与名称不同（如名称"2026级计算机2班"、代码"2622"），
    # 只显示名称时容易被误认为"班级不在下拉框里"。
    return {
        "items": [{"id": c.id, "name": c.name, "code": c.code, "major": c.major} for c in rows]
    }


def practice_data() -> dict:
    """返回静态练习资源常量（纯常量，不访问数据库，故无 db 参数）。"""
    return PRACTICE_DATA
