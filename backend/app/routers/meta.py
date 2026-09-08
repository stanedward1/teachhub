from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Classroom

router = APIRouter(prefix="/api/meta", tags=["公共"])


@router.get("/classes")
def class_options(school_id: int | None = None, db: Session = Depends(get_db)):
    """班级下拉选项（登录/注册时使用，无需登录）。仅返回未毕业班级。

    传入 school_id 时只返回该校班级（多租户下学生登录页按学校级联）。
    """
    q = db.query(Classroom).filter(Classroom.is_graduated.is_(False))
    if school_id:
        q = q.filter(Classroom.school_id == school_id)
    rows = q.order_by(Classroom.id).all()
    return {"items": [{"id": c.id, "name": c.name, "major": c.major} for c in rows]}


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


@router.get("/practice")
def practice_data():
    return PRACTICE_DATA
