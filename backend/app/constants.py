"""跨模块共享的业务常量。

与 `config.py` 的分工：`config.py` 承载**环境/部署配置**（可从环境变量覆盖），
本模块承载**业务口径**（属于产品定义，不应随部署环境变化）。

分数分段是全站唯一口径
----------------------
教务看板「成绩分布」、作业「分数段分布」、学情评语措辞三处必须共用 `SCORE_BANDS`，
**禁止在任何 service 内另立阈值表或另写 if 链**。

历史背景（`docs/REVIEW-2026-10-17-simplicity.md` S-01）：三处曾各有一套阈值
（教务 4 段 / 良好线 75，作业 5 段 / 良好线 80，评语裸写 90·75），导致同一分数
在不同页面落到不同等级——例如 78 分在教务看板显示「良好」、在作业分数段显示「中等」。
2026-10-18 经产品裁决统一为**五段、良好线 80**。
"""

# 五段，良好线 80。字段含义：
#   key     —— 稳定英文标识，供前端筛选与埋点引用（改动会影响前端状态，勿动）
#   label   —— 区间文案（图表/表格展示）
#   name    —— 中文档位名
#   min/max —— **闭区间**；全表按分数降序、首尾相连、完整覆盖 0-100
SCORE_BANDS = (
    {"key": "excellent", "label": "90-100", "name": "优秀", "min": 90, "max": 100},
    {"key": "good", "label": "80-89", "name": "良好", "min": 80, "max": 89},
    {"key": "medium", "label": "70-79", "name": "中等", "min": 70, "max": 79},
    {"key": "pass", "label": "60-69", "name": "及格", "min": 60, "max": 69},
    {"key": "fail", "label": "0-59", "name": "不及格", "min": 0, "max": 59},
)

# 关键分界线，由 SCORE_BANDS 派生——业务代码里不要再重写这些数字
EXCELLENT_LINE = SCORE_BANDS[0]["min"]  # 90
GOOD_LINE = SCORE_BANDS[1]["min"]  # 80
PASS_LINE = SCORE_BANDS[3]["min"]  # 60


def segment_index(score: int | float) -> int:
    """返回分数落在 ``SCORE_BANDS`` 中的下标（0=优秀 … 4=不及格）。

    这是**唯一的归段实现**。任何需要「某分属于第几段」的地方都应调用本函数，
    不要另写 if 链——否则又会多出一份阈值真源。

    越界兜底：``> 100`` 归入第 0 段，``< 0`` 归入最后一段。写入侧已有 0-100 校验，
    这里不抛异常，避免统计接口因单条脏数据整体 500。
    """
    for i, band in enumerate(SCORE_BANDS):
        if score >= band["min"]:
            return i
    return len(SCORE_BANDS) - 1
