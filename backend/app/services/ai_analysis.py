"""任务「AI 综合分析」：基于**逐生 AI 批改结论 + 教师评分 + 班级统计**给出班级层面的综合评价。

产品语境（教师端「分数段分布」弹窗里的「AI 综合分析」按钮）：教师已经看过逐生分数与逐生
AI 评语，缺的是**一屏能读完的班级结论** —— 整体水平、主要亮点、共性问题、下一步怎么教。
逐生批改（`ai_grading.grade_submission`）回答不了这个问题，所以这里单独做一次
「一个班一次调用」的聚合分析。

🔴 **送给模型的到底是什么（口径别写错，2026-11 审计 RDB-52）**：本模块**从不读学生提交
原文**。复核方式要**避开自指**（旧写法「grep "Submission" 应为 0 命中」把说明文字自己算了
进去，永远得到 1 —— RDB-66）：

```
grep -nE "Submission[.(]" app/services/ai_analysis.py   # 应为 0 命中：无提交正文取值
grep -n "^from app.models import" app/services/ai_analysis.py
# 输出里只有 AiGradingResult / Assignment / User，不含任何提交正文模型
```

输入只有四类：

1. 任务信息：标题 + 说明/正文（封顶 `_HEAD_CLIP_CHARS`）；
2. 班级统计：全部来自 `homework_service.score_distribution`；
3. 逐生明细行：姓名｜教师分｜AI 分｜`AiGradingResult.summary/strengths/improvements`；
4. 固定输出要求。

也就是说，模型看到的「学生写得怎么样」是 **AI 批改时留下的结论**（那份结论才是读过提交
正文的产物），不是提交本身。所以对外文案只能写「基于逐生 AI 批改结论 + 班级统计」，
写「基于已提交内容」是不实描述 —— 同一句谎话曾在模块 docstring、路由 docstring、
README、API.md（两处）、前端 api 注释与按钮提示共六处同时存在。

为什么不直接把提交正文也送进去：输入预算 `AI_MAX_INPUT_CHARS` 是 8000 字符（系统提示
也计入），一个班按 40 人算平均每人只剩不到 200 字 —— 送正文只会把每人切成一句半，
既做不出「共性问题」的归纳，又会让单次成本与同步等待时间随班级规模线性膨胀。
真要「按原文分析班级共性」，正确做法是离线汇总而不是把班级塞进一次同步外呼。

四条设计红线（照抄 `ai_grading` 的既有约定，不要在这里另立口径）：

1. **统计数字唯一真源是 `homework_service.score_distribution`**：分数口径（教师分优先、
   AI 分仅 success 兜底）、五段阈值（`app.constants.SCORE_BANDS`）、可见性与 404/403
   全由它决定。本模块**只读它的结果**，不重写聚合、不另设阈值 —— 否则同一个班在弹窗里
   和 AI 分析里会给出两套人数。
2. 🔴 **外呼唯一入口是 `ai_grading._call_model`**：项目铁律是「新增外呼入口 = 违规」。
   本模块**不得** import httpx、不得直接调 `ai_client.chat_completion`；`thinking` 由
   `_call_model` 统一关闭，这里也不再传。
3. **成本护栏照抄 `request_grading`**：总开关/学校闸/凭证 → **学校池先扣、平台池后扣**
   （双闸门，各预留 1 次）。这次分析算作**一次 AI 批改类调用**，与批改共用同一个成本池 ——
   额度是学校与平台的预算，分析不能白嫖。
4. **零提交必须在预留额度之前短路**：`reserve_*` 的语义是「预留即占用、失败不退还」
   （S21）。没有提交就没有可分析的内容，若先扣额度再报错，等于白吃教师一次额度。
   该路径必须**零额度消耗、零计数行写入**。

🔴 **同步外呼的等待上限（2026-11 审计 RBT-51）**：本接口是**同步**的（教师弹窗里线性
等待），而额度在 `reserve_*` 里就 commit 了（预留即占用）。因此「前端先超时 → 教师按
提示重试 → 后端仍在跑 → 再扣 1~2 次却拿不到结果」曾经是**必然路径**而非边界情况：前端
axios 全局 30 秒，后端单次 `AI_REQUEST_TIMEOUT=60`、截断重试后最坏 120 秒。现在两层兜住：

- 单次外呼上限改由 `settings.AI_ANALYSIS_TIMEOUT` 决定，与前端该请求的
  `ANALYSIS_TIMEOUT_MS = 180000` 满足 ``2 × 60 + 60 < 180`` 的余量关系；
- **在途去重**（`_acquire_inflight`）：同一任务已有一次分析在跑时，后来的请求直接 409
  且**不预留额度** —— 覆盖「客户端已放弃、服务端还在算」这段窗口，重试不会二次扣费。
  锁是**进程内**的（本服务单 worker 启动），跨进程不共享；它的价值是挡住重复点击，
  不是分布式锁。

输入预算（`settings.AI_MAX_INPUT_CHARS`，**系统提示词也计入**）：班级人多时逐生明细必然
超限，本模块按「五个分数段轮转取样」把有限预算公平地摊到各个分数段（避免只看到高分段的
样本就对全班下结论），并把**任何截断**写进 ``budget_notes`` 回给教师 —— 截断不允许静默发生。
"""
import logging
import threading
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AiGradingResult, Assignment, User
from app.models.ai import STATUS_SUCCESS
from app.platform_settings import get_ai_daily_limit, get_ai_max_tokens
from app.services import homework_service
from app.services.ai_client import AiClientError
from app.services.ai_grading import (
    _call_model,
    _school_pool_exhausted_reason,
    active_credential,
    can_grade,
    reserve_quota,
    reserve_school_quota,
    today_call_count,
)

logger = logging.getLogger("teachhub.ai")

# ---------------- 在途去重 ----------------
#: 正在生成分析的任务 id。**进程内**集合，配合 `_inflight_lock` 使用。
_inflight: set[int] = set()
_inflight_lock = threading.Lock()


def _acquire_inflight(assignment_id: int) -> None:
    """占住某任务的分析名额；已在跑则 409。

    🔴 必须放在 `reserve_*` **之前**：额度预留即 commit、失败不退还（S21），一次因
    「上一次还在跑」而被拒的请求绝不能扣掉教师的额度。它挡的正是「客户端 30 秒就放弃、
    服务端还在算 60~120 秒」那段窗口 —— 教师此时重试是最自然的动作，也是最容易二次扣费
    的动作。
    """
    with _inflight_lock:
        if assignment_id in _inflight:
            raise HTTPException(
                status_code=409,
                detail=(
                    "该任务的分析仍在生成中（上一次请求可能已在你这边超时），"
                    "本次不会消耗额度，请稍候再查看结果"
                ),
            )
        _inflight.add(assignment_id)


def _release_inflight(assignment_id: int) -> None:
    """释放名额。必须放在 ``finally`` 里：任何异常路径漏释放都会把该任务永久锁死。"""
    with _inflight_lock:
        _inflight.discard(assignment_id)


# ---------------- 提示词 ----------------
# 系统提示计入 `AI_MAX_INPUT_CHARS`，所以写得紧一点：只保留「不许编数字 / 不许罗列逐生
# 分数 / 不许编造姓名」这三条真正影响可用性的约束。
_SYSTEM_PROMPT = """你是中等职业学校计算机专业的教师教学分析助手。教师会给你一份某个班级某次任务的
数据摘要：任务信息、由系统统计好的班级数据，以及部分学生的分数与 AI 评语摘要。
请据此产出这份任务的**班级层面综合评价**，帮助教师看清整体情况、共性问题与下一步教学动作。

必须遵守：
- 统计数字（应提交/已提交/已评分/各分数段人数/均分/AI 覆盖率等）**已由系统计算并给出**，
  一律原样引用，**不得自行推算、重算或改写任何数字**，也不要新增摘要中没有的数字。
- 正文中**不要罗列逐生分数或逐生评语**，只做班级层面的归纳；举例最多 1-2 个典型现象，
  且**禁止编造学生姓名**（可以写「部分学生」「高分段学生」）。
- 只依据摘要中的信息推断，不得引入摘要之外的事实（学校政策、其他班级情况、教材进度等）。
- 语言务实、可落地：不要写「态度端正」「整体较好」这类没有信息量的空话。
- 用中文 Markdown 输出，四节小标题固定，不要增删或改名。"""

_OUTPUT_SPEC = """【输出要求】
严格按下面四节输出，用 Markdown 二级标题，全文 400-700 字：
## 总体情况
## 主要亮点
## 共性问题
## 教学建议"""

# 任务「说明 / 正文」合计最多送进模型这么多字符：它们是背景资料，本身可能是一整份任务单，
# 不封顶会把逐生明细挤出预算（与 `ai_grading` 的 head 预算同理）。
_HEAD_CLIP_CHARS = 600

# 逐生明细每行的字段裁剪上限（字符）。总评留 80 字足以看出问题类型；亮点/建议更短，
# 目的是让更多学生进入预算，而不是把某一个人的评语完整复述一遍。
_DETAIL_SUMMARY_CLIP = 80
_DETAIL_STRENGTH_CLIP = 40
_DETAIL_IMPROVEMENT_CLIP = 60

_DETAIL_TITLE = "【学生明细】（每行：姓名｜教师分｜AI分｜AI总评｜AI亮点｜AI建议；「—」表示无该项数据）"
_DETAIL_EMPTY_HINT = "（本次没有可参与分析的学生明细）"


def _flatten(text, limit: int) -> str:
    """把多行文本压成单行并截到 ``limit`` 字符（明细行必须一行一人，否则轮转取样失真）。"""
    if text is None:
        return ""
    flat = " ".join(str(text).split())
    if len(flat) <= limit:
        return flat
    # 预留 1 个字符给省略号，明确告诉模型「这条评语没看全」
    return flat[: max(0, limit - 1)] + "…"


def _score_text(value) -> str:
    """分数的文本形态：无分显示「—」（不能写成 0，0 是合法分数）。"""
    return "—" if value is None else str(value)


def _clip_head_text(assignment: Assignment | None) -> tuple[str, str, int]:
    """把任务「说明 / 正文」裁到 ``_HEAD_CLIP_CHARS`` 以内。

    Returns:
        ``(说明, 正文, 被截掉的字符数)``。两段都非空时用**水位法**（先各占一半，剩余额度
        让给对方），避免其中一段独吞预算 —— 与 `ai_grading._clip_assignment_head` 同思路，
        但这里是独立实现（不复用私有函数，避免服务间耦合）。
    """
    if assignment is None:
        return "", "", 0
    desc = (assignment.description or "").strip()
    cont = (assignment.content or "").strip()
    total = len(desc) + len(cont)
    if total <= _HEAD_CLIP_CHARS:
        return desc, cont, 0
    budget = _HEAD_CLIP_CHARS
    if not desc:
        return "", cont[:budget], total - budget
    if not cont:
        return desc[:budget], "", total - budget
    half = budget // 2
    d_keep = min(len(desc), half)
    c_keep = min(len(cont), max(0, budget - d_keep))
    d_keep = min(len(desc), max(0, budget - c_keep))
    return desc[:d_keep], cont[:c_keep], total - d_keep - c_keep


def _head_block(assignment: Assignment | None, title: str) -> tuple[str, int]:
    """任务信息块（标题 + 截断后的说明/正文）。返回 ``(文本, 被截掉的字符数)``。"""
    desc, cont, cut = _clip_head_text(assignment)
    parts = ["【任务信息】", f"标题：{title or '（未命名任务）'}"]
    if desc:
        parts.append(f"说明：{desc}")
    if cont:
        parts.append(f"正文：{cont}")
    if cut:
        parts.append(f"（任务说明/正文超出输入预算，已截断 {cut} 字符）")
    return "\n".join(parts), cut


def _stats_block(stats: dict) -> str:
    """班级统计块。数字全部来自 `score_distribution` 的返回值，本函数只做排版。"""
    segments = "｜".join(
        f"{s['name']}({s['label']}) {s['count']} 人" for s in stats["segments"]
    )
    avg_teacher = "—" if stats["avg_teacher_score"] is None else f"{stats['avg_teacher_score']}"
    avg_ai = "—" if stats["avg_ai_score"] is None else f"{stats['avg_ai_score']}"
    gap = "—" if stats["score_gap"] is None else f"{stats['score_gap']:+}"
    pct = "—" if stats["ai_reviewed_pct"] is None else f"{stats['ai_reviewed_pct']}%"
    return "\n".join(
        [
            "【班级统计】（以下数字由系统计算，请原样引用，不得改写）",
            (
                f"应提交 {stats['total']} 人｜已提交 {stats['submitted_count']} 人｜"
                f"已评分 {stats['scored_count']} 人｜已提交未评分 {stats['unscored_count']} 人｜"
                f"未交 {stats['unsubmitted_count']} 人"
            ),
            f"分数段人数：{segments}",
            (
                f"教师均分 {avg_teacher}｜AI 均分 {avg_ai}｜"
                f"教师分减 AI 分 {gap}"
            ),
            f"AI 已批改 {stats['ai_reviewed']} 人（占已提交 {pct}）",
        ]
    )


def _detail_line(
    name: str, teacher_score, ai_score, ai_result: AiGradingResult | None
) -> str:
    """一行学生明细：``姓名｜教师85｜AI82｜总评:…｜亮点:…｜建议:…``。

    AI 三个字段只在有 `status=success` 结果时才有内容（pending/failed 不参与），
    缺失统一写「—」，避免模型把空字段当成「AI 认为该生空白」。
    """
    summary = _flatten(getattr(ai_result, "summary", None), _DETAIL_SUMMARY_CLIP)
    strengths = _flatten(getattr(ai_result, "strengths", None), _DETAIL_STRENGTH_CLIP)
    improvements = _flatten(getattr(ai_result, "improvements", None), _DETAIL_IMPROVEMENT_CLIP)
    return (
        f"{_flatten(name, 20) or '学生'}"
        f"｜教师{_score_text(teacher_score)}"
        f"｜AI{_score_text(ai_score)}"
        f"｜总评:{summary or '—'}"
        f"｜亮点:{strengths or '—'}"
        f"｜建议:{improvements or '—'}"
    )


def _load_ai_results(db: Session, sub_ids: list[int]) -> dict:
    """取这批提交的**成功** AI 批改结果，返回 ``{submission_id: AiGradingResult}``。

    与 `homework_service.score_distribution` **同口径**：只按 `submission_id`（全局唯一）
    + ``status == success`` 过滤，**刻意不再补 `school_id` 条件**。两边必须一致 —— 同一条
    legacy 行（`ai_grading_results.school_id IS NULL`）若只被本函数排除，就会出现
    「stats 说 AI 已批改 2 人、明细里 AI 分也在，但总评/亮点/建议全是「—」」的两套口径
    （QA D-1：口径分叉比缺数据更难排查，教师会当成 AI 没给评语）。

    🔴 必须 ``skip_tenant_filter=True``：按 `submission_id` 定位足以确定唯一一行，带租户
    过滤只会把归属异常（`school_id` 为空）的历史行藏起来，表现为「明明批过、分析里全是 —」
    （与 `score_distribution` / `_upsert_result` 的处理一致）。

    越权风险由上游兜住：本函数的 `sub_ids` **全部来自 `score_distribution` 的返回值**，
    而它已做过租户过滤的 `db.get(Assignment, ...)` + `check_teacher_assignment_access`，
    因此不存在「顺着 id 读到别校结果」的路径。
    """
    if not sub_ids:
        return {}
    rows = (
        db.query(AiGradingResult)
        .execution_options(skip_tenant_filter=True)
        .filter(
            AiGradingResult.submission_id.in_(sub_ids),
            AiGradingResult.status == STATUS_SUCCESS,
        )
        .all()
    )
    return {row.submission_id: row for row in rows}


def _detail_buckets(distribution: dict, ai_results: dict) -> list[list[str]]:
    """把参与分析的学生按「五个分数段 + 未评分」分桶，每桶**按分数从低到高**排序。

    为什么先分桶再取样：一次性按名单顺序取前 N 个，取到的几乎总是学号靠前的同一批人；
    分桶轮转才能保证低分段和高分段都有代表性样本。
    未评分学生自成一桶（他们没有分数，无法归段，但「已提交未评分」本身是教师需要知道的
    信息，不能整体丢掉）。
    """
    buckets: list[list[str]] = []
    scored = distribution.get("scored_students") or []
    for idx in range(len(distribution.get("segments") or [])):
        rows = [r for r in scored if r.get("segment") == idx]
        rows.sort(key=lambda r: (r.get("score"), r.get("student_no") or ""))
        buckets.append(
            [
                _detail_line(
                    r.get("name"),
                    r.get("teacher_score"),
                    r.get("ai_score"),
                    ai_results.get(r.get("submission_id")),
                )
                for r in rows
            ]
        )
    unscored = distribution.get("unscored_students") or []
    if unscored:
        rows = sorted(unscored, key=lambda r: (r.get("student_no") or "", r.get("name") or ""))
        buckets.append(
            [
                _detail_line(
                    r.get("name"),
                    r.get("teacher_score"),
                    r.get("ai_score"),
                    ai_results.get(r.get("submission_id")),
                )
                for r in rows
            ]
        )
    return buckets


def _sample_details(buckets: list[list[str]], budget: int) -> tuple[list[str], int, int]:
    """按分数段**轮转**（round-robin）取明细行，直到预算耗尽。

    Args:
        buckets: 每个分数段一个列表（桶内已按分数升序）。
        budget: 明细可用的字符预算（已扣除系统提示、任务信息、统计块与输出要求）。

    Returns:
        ``(抽到的行, 参与分析的行数, 被跳过的行数)``。被跳过的人数必须回传给调用方
        写进 ``budget_notes`` —— 静默丢弃会让教师以为「AI 只看了 20 个学生」是全部。
    """
    total = sum(len(bucket) for bucket in buckets)
    if budget <= 0 or total == 0:
        return [], 0, total

    lines: list[str] = []
    used = 0
    cursors = [0] * len(buckets)
    while True:
        progressed = False
        for i, bucket in enumerate(buckets):
            if cursors[i] >= len(bucket):
                continue
            line = bucket[cursors[i]]
            cost = len(line) + 1  # +1：拼接时的换行符
            if used + cost > budget:
                # 本桶下一行放不下：本轮跳过它，让其它桶先把预算用满
                continue
            lines.append(line)
            used += cost
            cursors[i] += 1
            progressed = True
        if not progressed:
            break
    taken = len(lines)
    return lines, taken, total - taken


def _build_messages(
    buckets: list[list[str]], head: str, stats_text: str, limit: int
) -> tuple[list[dict], list[str], int, bool, int]:
    """组装一次分析调用的 messages，并保证**总字符量 ≤ limit**（系统提示也计入）。

    预算分配顺序：系统提示 → 任务信息（已封顶 600 字）→ 统计块（**永不裁剪**，它是
    数字唯一来源）→ 逐生明细（吃剩余预算）→ 输出要求（固定结构，必须保留）。

    Returns:
        ``(messages, 预算说明列表, 被跳过的明细行数, 是否发生截断, 实际参与的行数)``。
    """
    notes: list[str] = []

    def assemble(lines: list[str]) -> str:
        body = lines if lines else [_DETAIL_EMPTY_HINT]
        return "\n".join([head, stats_text, _DETAIL_TITLE, *body, _OUTPUT_SPEC])

    # 先算「骨架」留给明细的空间：系统提示 + 任务信息 + 统计块 + 明细标题 + 输出要求
    fixed = len(_SYSTEM_PROMPT) + len(assemble([""]))
    budget = limit - fixed
    lines, taken, omitted = _sample_details(buckets, budget)
    user_text = assemble(lines)

    # 兜底一：骨架本身超限（limit 被调得很小）。先牺牲任务说明/正文，保留统计与输出要求。
    if len(user_text) + len(_SYSTEM_PROMPT) > limit:
        trimmed_head = head.split("\n")[1:2] if head else []  # 只留「标题：…」一行
        candidate = "\n".join(["【任务信息】", *trimmed_head]) if trimmed_head else ""
        if candidate and len(candidate) < len(head):
            notes.append(f"任务说明/正文因输入预算不足已整体省略 {len(head)} 字符")
            head = candidate
            user_text = assemble(lines)

    # 兜底二：仍超限（明细行极长 / limit 极小）→ 从尾部丢明细行，丢了多少如实上报。
    dropped = 0
    while len(user_text) + len(_SYSTEM_PROMPT) > limit and lines:
        lines.pop()
        dropped += 1
        user_text = assemble(lines)
    omitted += dropped
    taken -= dropped

    # 终极兜底：连骨架都放不下 ⇒ 按字符切，但**输出契约（四节标题）必须保住**：
    # 把 `_OUTPUT_SPEC` 一起切掉，模型就可能不按四节写，省下的字符换来一份没法用的正文。
    truncated = omitted > 0
    if len(user_text) + len(_SYSTEM_PROMPT) > limit:
        spec_part = "\n" + _OUTPUT_SPEC
        core = (
            user_text[: -len(spec_part)] if user_text.endswith(spec_part) else user_text
        )
        budget_for_core = max(0, limit - len(_SYSTEM_PROMPT) - len(spec_part))
        user_text = core[:budget_for_core] + spec_part
        notes.append("分析请求仍超出输入预算，已从尾部截断（未显示的内容未参与本次分析）")
        truncated = True
        if len(user_text) + len(_SYSTEM_PROMPT) > limit:
            # 极限情况：预算连「系统提示 + 输出要求」都装不下，只能硬切并明说要调大配置
            user_text = user_text[: max(0, limit - len(_SYSTEM_PROMPT))]
            notes.append(
                "输入预算过小（AI_MAX_INPUT_CHARS），连输出要求都无法完整下发，请调大该配置"
            )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]
    return messages, notes, omitted, truncated, taken


def _stats_from_distribution(distribution: dict) -> dict:
    """从 `score_distribution` 的返回值计算分析用的统计块（**不做任何口径判断**）。"""
    submitted = int(distribution.get("submitted_count") or 0)
    rows = (distribution.get("scored_students") or []) + (
        distribution.get("unscored_students") or []
    )
    teacher_scores = [r["teacher_score"] for r in rows if r.get("teacher_score") is not None]
    ai_scores = [r["ai_score"] for r in rows if r.get("ai_score") is not None]
    avg_teacher = (
        round(sum(teacher_scores) / len(teacher_scores), 1) if teacher_scores else None
    )
    avg_ai = round(sum(ai_scores) / len(ai_scores), 1) if ai_scores else None
    ai_reviewed = len(ai_scores)
    return {
        "total": distribution.get("total"),
        "submitted_count": submitted,
        "scored_count": distribution.get("scored_count"),
        "unscored_count": distribution.get("unscored_count"),
        "unsubmitted_count": distribution.get("unsubmitted_count"),
        "segments": [
            {
                "key": s.get("key"),
                "name": s.get("name"),
                "label": s.get("label"),
                "count": s.get("count"),
            }
            for s in (distribution.get("segments") or [])
        ],
        # 均分与差值保留 1 位小数；无数据一律 None（不用 0 冒充「平均 0 分」）
        "avg_teacher_score": avg_teacher,
        "avg_ai_score": avg_ai,
        # 正数 = 教师给分高于 AI；负数 = 教师较严
        "score_gap": (
            round(avg_teacher - avg_ai, 1)
            if avg_teacher is not None and avg_ai is not None
            else None
        ),
        "ai_reviewed": ai_reviewed,
        "ai_reviewed_pct": (
            round(ai_reviewed * 100 / submitted, 1) if submitted > 0 else None
        ),
    }


def _run_analysis(
    db: Session,
    *,
    assignment_id: int,
    assignment: Assignment | None,
    distribution: dict,
    title: str,
    school_id: int | None,
    cred,
) -> dict:
    """预留双池额度 → 组装摘要 → 外呼 → 返回结果。**调用方必须已通过全部闸门**。

    拆成独立函数只为让 `analyze_assignment` 用 ``try/finally`` 包住「在途名额」:
    从预留额度到外呼结束之间的任何异常路径都必须释放名额，否则该任务会被永久锁死
    （后续请求一律 409，且都不会再去释放它）。
    """
    # 双闸门预留在后（学校池先扣、平台池后扣，顺序照抄 `request_grading`）：
    # `can_grade` 只是前置检查，真正的护栏是这两个原子预留。
    if reserve_school_quota(db, school_id, 1) <= 0:
        raise HTTPException(status_code=400, detail=_school_pool_exhausted_reason(db, school_id))
    if reserve_quota(db, 1) <= 0:
        # 平台池在 can_grade 通过后、预留前被并发吃空：给出真实原因（额度耗尽）。
        # 学校池已扣的份额按 S21 不退还（宁可少分析一次，不可超支）。
        raise HTTPException(
            status_code=400,
            detail=f"今日调用已达上限（{today_call_count(db)}/{get_ai_daily_limit(db)}）",
        )

    stats = _stats_from_distribution(distribution)
    sub_ids = [
        r["submission_id"]
        for r in (distribution.get("scored_students") or [])
        + (distribution.get("unscored_students") or [])
        if r.get("submission_id")
    ]
    ai_results = _load_ai_results(db, sub_ids)
    # 一次性取完所有 DB 侧输入：外呼前要把连接还回池，rollback 之后任何 ORM 属性访问
    # 都会重新开一段事务（见下方 🔴）
    max_tokens = get_ai_max_tokens(db)

    head, head_cut = _head_block(assignment, title)
    stats_text = _stats_block(stats)
    buckets = _detail_buckets(distribution, ai_results)
    total_rows = sum(len(bucket) for bucket in buckets)

    limit = settings.AI_MAX_INPUT_CHARS
    messages, budget_notes, omitted, truncated, taken = _build_messages(
        buckets, head, stats_text, limit
    )
    if head_cut:
        budget_notes.insert(0, f"任务说明/正文超出输入预算，已截断 {head_cut} 字符")
        truncated = True
    if omitted > 0:
        budget_notes.append(
            f"学生明细超出输入预算，已按分数段轮转抽取 {taken}/{total_rows} 人，"
            "其余未参与本次分析"
        )

    # 🔴 外呼前结束只读事务，把连接还回池（RBT-67）：`reserve_*` 内部 commit 过，但之后
    # `_load_ai_results` / `get_ai_max_tokens` 又开了一段隐式事务并**一直攥着** 1 条连接；
    # `_call_model` 最长 2×AI_ANALYSIS_TIMEOUT（60s×2），这段窗口里 Session 处于
    # idle-in-transaction。池上限 `pool_size=10 + max_overflow=20` ⇒ 并发 30 个分析请求
    # 就能吃满整池，其余接口全部排队等连接（`SLOW SQL` 只统计语句执行时间，看不见这种
    # 「闲在事务里」的占用）。
    # 位置很关键：必须**在所有取数与文本组装之后**（上面 `_head_block` 读的是 `assignment`
    # 的 ORM 属性，rollback 会过期它并触发一次补查，等于重新占住连接），且 `max_tokens`
    # 已提前取出；此后到外呼返回之间不再访问任何 ORM 对象。
    db.rollback()

    try:
        response = _call_model(
            cred,
            messages,
            max_tokens,
            db=db,
            school_id=school_id,
            # 同步链路必须传自己的上限：最坏 2 次外呼，见模块 docstring 的等待上限一节。
            timeout=settings.AI_ANALYSIS_TIMEOUT,
        )
    except AiClientError as exc:
        raise HTTPException(status_code=502, detail=f"AI 分析失败：{exc}") from exc

    content = (response.get("content") or "").strip()
    if not content:
        # 空正文绝不能当成功返回：教师会看到一张标题下的空白卡片，比报错更难排查
        raise HTTPException(status_code=502, detail="AI 分析失败：AI 未返回有效内容")

    usage = response.get("usage") or {}
    logger.info(
        "AI 综合分析完成 assignment=%s 参与学生=%s 未参与=%s prompt_tokens=%s",
        assignment_id,
        taken,
        omitted,
        usage.get("prompt_tokens"),
    )
    return {
        "assignment_id": assignment_id,
        "assignment_title": title,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stats": stats,
        "analysis": content,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "elapsed_ms": response.get("elapsed_ms"),
        },
        "budget_notes": budget_notes,
        "omitted_count": omitted,
        "truncated": bool(truncated or omitted > 0 or head_cut),
    }


def analyze_assignment(db: Session, assignment_id: int, user: User) -> dict:
    """生成某任务（某班）的 AI 综合分析。**每次调用消耗 1 次 AI 额度**。

    闸门顺序（与 `ai_grading.request_grading` 保持同一套，勿调换）：

    1. `homework_service.score_distribution` —— 404 / 403 / 租户隔离的唯一真源；
    2. **零提交短路**（必须在任何额度预留之前，见模块 docstring 第 4 条）；
    3. 凭证 → 总开关/学校闸/额度前置（`can_grade`）；
    4. **在途去重**（`_acquire_inflight`，同样在预留之前：被拒的请求不扣额度）；
    5. 学校池预留 → 平台池预留（各 1 次，双闸门，任一不足即 400）；
    6. 组装带预算的数据摘要 → `ai_grading._call_model`（唯一外呼入口）。

    Args:
        db: 数据库会话。
        assignment_id: 任务 id。
        user: 当前登录用户（教师 / 学校管理员 / 平台超管）。

    Returns:
        形如 ``{assignment_id, assignment_title, generated_at, stats, analysis, usage,
        budget_notes, omitted_count, truncated}`` 的 dict。

    Raises:
        HTTPException: 404 任务不存在；403 无权访问；400 零提交 / 未配置 / 额度不足；
            409 同一任务已有一次分析在跑（**本次不扣额度**）；
            502 模型调用失败或未返回有效内容。
    """
    distribution = homework_service.score_distribution(db, assignment_id, user)
    submitted_count = int(distribution.get("submitted_count") or 0)
    if submitted_count <= 0:
        # 🔴 这条必须在 `reserve_*` 之前：额度预留即占用且不退还（S21），
        # 无提交可分析时白扣一次额度是对成本护栏的直接破坏。
        raise HTTPException(status_code=400, detail="该任务还没有学生提交，无法生成分析")

    assignment = db.get(Assignment, assignment_id)
    school_id = assignment.school_id if assignment is not None else None
    title = distribution.get("assignment_title") or (assignment.title if assignment else "")

    # 凭证先行：文案面向教师（谁该去找管理员），与 `can_grade` 的原因串互补而不冲突。
    # 取到后存成局部变量复用到底：第二次 `active_credential(db)` 既多一次查询，也留了
    # 「两次调用之间凭证被停用 ⇒ 把 None 传给 `_call_model`」的窗口。
    cred = active_credential(db)
    if cred is None:
        raise HTTPException(status_code=400, detail="AI 服务未配置，请联系管理员")

    allowed, reason = can_grade(db, school_id)
    if not allowed:
        raise HTTPException(status_code=400, detail=reason or "当前无法发起 AI 分析")

    # 🔴 在途去重必须在预留之前（见 `_acquire_inflight`）：被 409 挡下的请求一旦先扣了
    # 额度，就成了「什么都没做却扣了 1~2 次」——正是本条要消灭的路径。
    _acquire_inflight(assignment_id)
    try:
        return _run_analysis(
            db,
            assignment_id=assignment_id,
            assignment=assignment,
            distribution=distribution,
            title=title,
            school_id=school_id,
            cred=cred,
        )
    finally:
        _release_inflight(assignment_id)
