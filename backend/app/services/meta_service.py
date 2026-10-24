"""公共元数据业务逻辑（B1 分层：自 routers/meta.py 下沉，行为完全不变）。"""
from sqlalchemy.orm import Session

from app.models import Classroom

# ---- 学习资源清单（纯静态常量，不查库）----
# 所有外链均于 2026-10-23 实测返回 HTTP 200；新增/替换条目前请同样验证，避免给学生放出死链。
# 特别注意：中国日报必须用 www 域（`https://cn.chinadaily.com.cn/` 的 HTTPS 实测连接失败）。
_OJ_LINKS = [
    {"name": "洛谷", "url": "https://www.luogu.com.cn", "desc": "国内最大的 OJ，题目分级清晰，新手友好"},
    {"name": "PTA", "url": "https://pintia.cn", "desc": "浙大出品，配套课程题库，适合随堂练习"},
    {"name": "牛客网", "url": "https://www.nowcoder.com", "desc": "算法竞赛与面试题，社区活跃"},
    {"name": "力扣 LeetCode", "url": "https://leetcode.cn", "desc": "算法入门到进阶，题解丰富"},
    {"name": "Codeforces", "url": "https://codeforces.com", "desc": "国际知名算法竞赛平台"},
]

_TUTORIAL_LINKS = [
    {"name": "C 语言入门教程", "url": "https://www.runoob.com/cprogramming/c-tutorial.html", "desc": "零基础 C 语言图文教程"},
    {"name": "C 语言中文网", "url": "https://c.biancheng.net", "desc": "系统全面的 C 语言学习站"},
    {"name": "翁恺 C 语言课程", "url": "https://www.icourse163.org", "desc": "浙大翁恺老师的经典 C 语言 MOOC"},
]

_TYPING_LINKS = [
    {"name": "打字鸭", "url": "https://daziya.com/", "desc": "免费打字练习：指法、拼音、中文文章与英文单词"},
    {"name": "打字鸭 · 标准指法课程", "url": "https://typingfun.cn/courses/1", "desc": "从基准键开始的阶梯式课程，适合零基础"},
]

_NEWS_LINKS = [
    {"name": "中国新闻网", "url": "https://www.chinanews.com.cn/", "desc": "中新社主办，图片频道更新快，社会与教育图集多"},
    {"name": "光明网", "url": "https://www.gmw.cn/", "desc": "教育、文化、科技版块强，图片质量高"},
    {"name": "人民网", "url": "https://www.people.com.cn/", "desc": "权威综合站，长文配图完整，适合阅读课"},
    {"name": "新华网", "url": "https://www.news.cn/", "desc": "快讯更新快，首页大图编排好"},
    {"name": "中国青年报", "url": "https://zqb.cyol.com/", "desc": "面向青年的央媒，校园与就业话题贴近"},
    {"name": "中国新闻图片网", "url": "https://www.cnsphoto.com/", "desc": "纯新闻摄影图库，可学构图与视觉表达"},
]

_LAW_LINKS = [
    {"name": "中国法治网", "url": "https://www.legaldaily.com.cn/", "desc": "法制日报社主办，法治新闻与案例报道"},
    {"name": "智慧普法平台", "url": "https://legalinfo.moj.gov.cn/", "desc": "司法部主办，反诈、未成年人保护等普法专题"},
]

_SCIENCE_LINKS = [
    {"name": "科普中国", "url": "https://www.kepuchina.cn/", "desc": "中国科协主办，前沿科技与科学辟谣"},
    {"name": "中国科技网", "url": "https://www.stdaily.com/", "desc": "科技日报旗下，技术落地与产业动态"},
]

_CAREER_LINKS = [
    {"name": "国家职业教育智慧教育平台", "url": "https://vocational.smartedu.cn/", "desc": "教育部主办，中职专业课与虚拟仿真实训免费开放"},
    {"name": "中国教育报", "url": "https://www.jyb.cn/", "desc": "教育部主管，教育政策与升学信息图文解读"},
]

PRACTICE_DATA = {
    # 分组资源（2026-10-23）：前端按 groups 顺序渲染卡片，不猜分类。
    # 每个分组只描述「教学语义」（key / title / note / links），**不含图标名**——
    # 图标属于展示层，由前端按 key 映射，避免后端承担 UI 细节。
    "groups": [
        {
            "key": "coding",
            "title": "编程练习",
            "note": "在线评测平台，边学边练",
            "links": _OJ_LINKS,
        },
        {
            "key": "tutorial",
            "title": "C 语言入门教程",
            "note": "从零基础到能写完整程序",
            "links": _TUTORIAL_LINKS,
        },
        {
            "key": "typing",
            "title": "打字练习",
            "note": "指法、盲打与中文输入",
            "links": _TYPING_LINKS,
        },
        {
            "key": "news",
            "title": "图文新闻",
            "note": "长文配图，顺带练阅读与打字材料",
            "links": _NEWS_LINKS,
        },
        {
            "key": "law",
            "title": "法治与思政",
            "note": "法治新闻与普法专题",
            "links": _LAW_LINKS,
        },
        {
            "key": "science",
            "title": "科普与科技",
            "note": "科技前沿与科学辟谣",
            "links": _SCIENCE_LINKS,
        },
        {
            "key": "career",
            "title": "升学与就业",
            "note": "职业教育资源与教育政策",
            "links": _CAREER_LINKS,
        },
    ],
    # 兼容 2026-10-23 之前的旧字段（旧前端读 oj / tutorials）。与 groups 引用**同一列表对象**，
    # 因此不构成第二份定义，改数据只需改上面那七个常量。
    "oj": _OJ_LINKS,
    "tutorials": _TUTORIAL_LINKS,
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
    """返回学习资源分组常量（纯常量，不访问数据库，故无 db 参数）。

    结构：`{groups: [{key, title, note, links: [{name, url, desc}]}], oj, tutorials}`。
    后两个字段是为旧前端保留的兼容别名（与 groups 内引用同一列表对象）。
    """
    return PRACTICE_DATA
