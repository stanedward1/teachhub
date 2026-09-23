"""AI 作业批改：触发、执行、结果落库、降级。

链路：**教师点击「AI 批改」** → `homework_service.ai_grade_*`（校验班级归属）
→ `request_grading`（校验总开关/凭证/额度）→ 线程池 →
`_run_grading`（**新 session + 显式租户上下文**）→ 写 `ai_grading_results`。

🔴 **批改是纯手动触发，学生提交不产生任何外呼**：
`homework_service.submit` 里**没有**批改调用 —— 教学场景中教师需要先看学生交了没有、
交了什么，再决定是否花额度批改；自动批改还会在「学生反复重交」时重复烧额度。

三条硬约束（docs/AI-GRADING-PRD.md §6 F3 / §7.2）：

1. **不阻塞请求**：批改全部在后台线程执行；触发线程只做几次廉价的配置读取
   （开关 / 凭证 / 限额），不做任何网络调用，接口立即返回。
2. **降级彻底**：超时、5xx、未配置凭证、总开关关闭、额度耗尽、附件解析失败 —— 任一情形下
   都只把原因记进结果行给教师看，**不影响学生提交，也不向学生暴露任何 AI 错误**。
3. 🔴 **后台线程必须显式设置租户上下文**：HTTP 中间件只作用于请求线程，
   线程池里 `ContextVar` 可能是空的或残留别的租户。不设置会导致 ORM 过滤失效
   （跨校串数据）或查不到数据。这是本项目最易踩的坑。
"""
import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import settings
from app.crypto import decrypt_secret
from app.models import (
    AiCredential,
    AiGradingResult,
    AiUsageDaily,
    Assignment,
    AssignmentAttachment,
    ExcellentWork,
    Submission,
    User,
)
from app.platform_settings import (
    get_ai_auto_publish_owner,
    get_ai_daily_limit,
    get_ai_max_tokens,
    is_ai_auto_publish_enabled,
    is_ai_grading_enabled,
)
from app.services.ai_attachments import extract_attachment, extract_inline_images
from app.services.ai_client import AiClientError, chat_completion
from app.tenant import tenant_scope

logger = logging.getLogger("teachhub.ai")

# 后台批改线程数：批改是 I/O 密集（等模型返回），2 个并发足以消化一个班的提交量，
# 又不会把上游服务打爆或抢占太多连接。
_MAX_WORKERS = 2
_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="ai-grading")

_SYSTEM_PROMPT = """你是一位经验丰富的中小学教师，正在批改学生的上机作业。

【评价依据】
只依据本条消息中的【作业要求】、【任务附件】、【学生提交内容】、【附件内容】，以及随消息附上的图片
进行评价。不得引入外部知识去臆测提交中并不存在的内容。

【反幻觉要求（必须严格遵守）】
- 若提交内容为空、截断后已无有效信息，或图片缺失/无法辨认/未附带，必须如实说明
  「资料不足，无法评价」，并把 strengths 与 improvements 置为空字符串，**禁止编造亮点**；
- 若提交内容与作业要求明显无关（例如要求上机编程、却只交了一张无关照片），应在 summary
  中直接指出「提交内容与作业要求不符」，不要强行找优点、也不要把无关内容夸成创新；
- 不要罗列放之四海而皆准的空话（如「态度端正」「界面美观」）充当优点，
  每一条优点都必须能对应到提交里的具体内容；
- 正文中的【图片N】标记与随消息附上的图片按顺序一一对应；若某张图片标注为
  「未参与批改」，说明你没看到它，不得凭空评价该图。

只输出一个 JSON 对象，不要输出任何其它文字，不要使用 Markdown 代码围栏。
JSON 结构如下：
{
  "score": 0 到 100 的整数（若无法判断则为 null）,
  "summary": "总体评价，80-200 字",
  "strengths": "优点，分条书写，每条以 - 开头；资料不足时为空字符串",
  "improvements": "改进建议，分条书写，每条以 - 开头；资料不足时为空字符串",
  "excellent": true 或 false（是否达到可在班级内展示的优秀水平）,
  "excellent_reason": "excellent 为 true 时说明理由，否则为空字符串"
}

评分参考维度：完成度、正确性、规范性、创造性。"""


# ---------------- 输出解析 ----------------
def _slice_json(text: str) -> str:
    """截取首个 `{` 到末个 `}` 之间的片段（应对模型在 JSON 前后加了解释）。"""
    start = text.find("{")
    end = text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else ""


def _as_text(value) -> str:
    """把模型字段归一化成文本（兼容字符串 / 数组 / 空值）。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return str(value)


def parse_model_output(content: str) -> dict:
    """解析模型返回内容为结构化字段。

    容错策略：先剥 Markdown 围栏，再整体解析，再退化为「截取花括号片段」解析；
    全部失败时**不丢弃内容**，把原文当作总评返回（宁可信息粗糙，也不要空结果）。
    """
    text = (content or "").strip()
    stripped = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    stripped = re.sub(r"\s*```$", "", stripped)

    parsed = None
    for candidate in (stripped, _slice_json(stripped)):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            parsed = data
            break

    if parsed is None:
        return {
            "score": None,
            "summary": text[:2000],
            "strengths": "",
            "improvements": "",
            "is_excellent_candidate": False,
            "excellent_reason": "",
            "parsed": False,
        }

    score = parsed.get("score")
    try:
        score = int(score) if score is not None else None
    except (TypeError, ValueError):
        score = None
    if score is not None and not 0 <= score <= 100:
        score = None

    return {
        "score": score,
        "summary": _as_text(parsed.get("summary")),
        "strengths": _as_text(parsed.get("strengths")),
        "improvements": _as_text(parsed.get("improvements")),
        "is_excellent_candidate": bool(parsed.get("excellent")),
        "excellent_reason": _as_text(parsed.get("excellent_reason")),
        "parsed": True,
    }


# ---------------- 配置与限额 ----------------
def active_credential(db: Session) -> AiCredential | None:
    """取当前可用凭证（已启用且密钥可解密）；不可用返回 None。

    凭证表不含 `school_id`，不受租户过滤影响。
    """
    cred = db.query(AiCredential).order_by(AiCredential.id.desc()).first()
    if cred is None or not cred.enabled:
        return None
    if not decrypt_secret(cred.api_key_encrypted):
        return None
    return cred


def _db_today(db: Session) -> date:
    """取**数据库时钟**下的当天日期。

    额度统计必须与 `created_at` 用同一时间基准，否则会出现「进程本地凌晨 = 数据库
    前一天」的错位（SQLite 存 UTC、MySQL 存库本地时区，而 Python 取进程本地日期）。
    SQLite 的 `CURRENT_DATE` 返回字符串，MySQL 返回 `date`，这里统一成 `date`。
    """
    raw = db.execute(select(func.current_date())).scalar()
    if isinstance(raw, date):
        return raw
    return date.fromisoformat(str(raw)[:10])


def today_call_count(db: Session) -> int:
    """当日已**预留**的批改外呼次数（平台级口径，跨租户统计）。

    读 `ai_usage_daily` 而**不是**数 `ai_grading_results` 行数 —— 后者会被
    「重跑 upsert 覆盖同一行」与「学生重交删行」扭曲，使额度这一唯一成本刹车失真
    （详见 `AiUsageDaily` 的 docstring）。本口径与结果行的生命周期解耦，只增不减。
    """
    row = db.query(AiUsageDaily).filter(AiUsageDaily.day == _db_today(db)).first()
    return int(row.call_count or 0) if row else 0


def remaining_quota(db: Session) -> int:
    """今日剩余可批改次数（平台级口径，跨租户统计；额度耗尽返回 0）。"""
    return max(get_ai_daily_limit(db) - today_call_count(db), 0)


def reserve_quota(db: Session, n: int) -> int:
    """**原子**预留 `n` 次额度，返回实际预留成功的次数（<= n）。

    为什么必须原子：`request_grading` 原本是「查剩余额度 → 截断 → 投递」，两次并发
    请求会各自读到同一份剩余额度并各自满额投递 ⇒ 实际外呼可达额度的 2 倍，护栏失效。
    这里对当天计数行加行锁（`SELECT ... FOR UPDATE`；SQLite 为单线程测试环境，
    不支持该子句、SQLAlchemy 会静默忽略，语义仍正确），在锁内重读并只在额度内自增，
    把「检查 + 占用」合成为一个原子操作。

    语义：预留即代表**将要发生**一次外呼，因此额度在投递前就被占用；任务随后失败
    也不回退 —— 这是成本护栏应有的方向（宁可少批，不可超支）。
    """
    if n <= 0:
        return 0
    limit = get_ai_daily_limit(db)
    if limit <= 0:
        return 0
    day = _db_today(db)

    row = db.query(AiUsageDaily).filter(AiUsageDaily.day == day).with_for_update().first()
    if row is None:
        # 首次创建当天行：并发下可能撞 `day` 唯一索引，用 SAVEPOINT 包住以便安全重读
        try:
            with db.begin_nested():
                db.add(AiUsageDaily(day=day, call_count=0))
            db.commit()
        except IntegrityError:
            db.rollback()
        row = (
            db.query(AiUsageDaily)
            .filter(AiUsageDaily.day == day)
            .with_for_update()
            .first()
        )
        if row is None:
            return 0

    used = int(row.call_count or 0)
    take = max(0, min(n, limit - used))
    if take:
        row.call_count = used + take
        db.commit()
    return take


def can_grade(db: Session) -> tuple[bool, str]:
    """判断当前是否允许发起批改，返回 ``(是否允许, 原因)``。"""
    if not is_ai_grading_enabled(db):
        return False, "AI 批改总开关未开启"
    if active_credential(db) is None:
        return False, "AI 凭证未配置、未启用或密钥不可用"
    if remaining_quota(db) <= 0:
        return False, f"今日调用已达上限（{today_call_count(db)}/{get_ai_daily_limit(db)}）"
    return True, ""


# ---------------- 结果落库 ----------------
def _upsert_result(
    db: Session, submission_id: int, school_id: int | None = None, **fields
) -> AiGradingResult:
    """按 `submission_id` 更新或新建结果行（重跑覆盖，天然幂等）。

    `school_id` 仅在传入且当前为空时回填：绝不覆盖已有的非空归属，
    避免把正确归属的租户数据误写成 NULL（后台线程租户上下文为 None 时
    ORM `before_flush` 自动填充是空操作，结果行会落成对所有租户不可见）。
    """
    result = (
        db.query(AiGradingResult)
        # 必须跳过租户过滤：`submission_id` 是**全局唯一**键，结果行的身份与租户无关。
        # 否则归属异常的行（如租户上下文为 None 时预写落下的 `school_id=NULL`）
        # 读不到 → 走 INSERT → 撞 `uq_ai_grading_submission` 报 1062，
        # 且失败降级也写不进去 → 整批不可恢复（2026-09-22 线上事故）。
        .execution_options(skip_tenant_filter=True)
        .filter(AiGradingResult.submission_id == submission_id)
        .first()
    )
    if result is None:
        result = AiGradingResult(submission_id=submission_id)
        db.add(result)
    # 显式归属：仅在非空且当前为空时回填，绝不覆盖已有归属
    if school_id is not None and result.school_id is None:
        result.school_id = school_id
    for key, value in fields.items():
        setattr(result, key, value)
    return result


# 任务附件文本可占用的输入预算比例（相对于 AI_MAX_INPUT_CHARS）。
# 附件可能是整本教材，不能让它把学生的提交内容挤出输入上限。
_ASSIGNMENT_ATTACHMENT_BUDGET_RATIO = 0.25

# 无论教师传了多少张任务附件图片，**至少为学生自己的材料（提交附件 / 正文内嵌）保留 1 个
# 图片名额**。否则「老师传了 6 张参考图 → 学生交的东西一张都进不去」，批改会彻底失去依据。
_RESERVED_IMAGE_SLOTS_FOR_SUBMISSION = 1


def _extract_assignment_materials(
    assignment: Assignment | None,
    *,
    vision_enabled: bool,
    max_images: int,
) -> tuple[str, list[str], list[str]]:
    """抽取**教师布置任务时上传的附件**（`assignment_attachments`，一对多）。

    为什么必须有：上机任务常把要求写在附件里（docx / pdf），而 `description` 与
    `content` 留空。此前批改只读 `assignment.title/description/content`，模型看到的
    【作业要求】几乎是空的 —— 只能对着学生提交内容凭空找亮点，教师侧表现为
    「批得头头是道，但完全没按任务要求」（实现缺口，与 PRD §8 Q4「附件纳入批改」不一致）。

    沿用 `extract_attachment` 的降级约定：**永不抛异常**，解析失败只写说明。
    文本总量另设预算（`_ASSIGNMENT_ATTACHMENT_BUDGET_RATIO`）。

    Returns:
        `(拼接后的附件文本, 图片 data URL 列表, 逐条说明)`。
        说明统一加 `[任务]` 前缀，与**学生**提交附件的说明区分开
        （后者无前缀），最终落到 `attachment_used` 供教师查看。
    """
    if assignment is None or not assignment.attachments:
        return "", [], []

    text_budget = int(settings.AI_MAX_INPUT_CHARS * _ASSIGNMENT_ATTACHMENT_BUDGET_RATIO)
    texts: list[str] = []
    images: list[str] = []
    notes: list[str] = []
    used = 0
    truncated = False

    for att in assignment.attachments:
        if len(images) >= max_images:
            notes.append(f"[任务]图片附件超出单次张数上限，未参与批改（{att.filename}）")
            continue
        payload = extract_attachment(
            att.filepath, att.filename, vision_enabled=vision_enabled
        )
        if payload.note:
            notes.append(f"[任务]{payload.note}")
        if payload.images:
            images.extend(payload.images)
        if not payload.text:
            continue
        remaining = text_budget - used
        if remaining <= 0:
            truncated = True
            continue
        chunk = payload.text[:remaining]
        if len(chunk) < len(payload.text):
            truncated = True
        used += len(chunk)
        texts.append(f"—— {att.filename} ——\n{chunk}")

    if truncated:
        notes.append("[任务]附件文本超出输入预算，已截断")
    return "\n\n".join(texts), images, notes


def _build_messages(
    assignment: Assignment | None,
    content_text: str,
    attachment_text: str,
    images: list[str],
    requirement_text: str = "",
) -> list[dict]:
    """构造批改请求消息（作业要求 + 任务附件 + 学生正文 + 学生附件 + 图片）。

    ``content_text`` 是**已把内嵌图片换成占位说明**的正文（见
    `ai_attachments.extract_inline_images`），不再直接取 `submission.content` ——
    否则正文里的图片引用（``![](/uploads/x.png)``）对模型只是一串访问不到的 URL。

    ``requirement_text`` 是**教师任务附件**抽取出的文本（见
    `_extract_assignment_materials`）：上机任务常把要求写在附件里、`description`
    留空，缺了它【作业要求】就是空的。
    """
    parts: list[str] = ["【作业要求】"]
    if assignment is not None:
        parts.append(f"标题：{assignment.title}")
        if assignment.description:
            parts.append(f"说明：{assignment.description}")
        if assignment.content:
            parts.append(f"正文：\n{assignment.content}")
        if requirement_text:
            parts.append(f"\n【任务附件】\n{requirement_text}")
        elif not (assignment.description or "").strip() and not (
            assignment.content or ""
        ).strip():
            # 既无文字说明也无可用任务附件：必须显式告知，否则模型会自己编一套评分标准，
            # 而教师看到的是一份「有模有样但无依据」的批改（比报错更危险）。
            parts.append(
                "\n（⚠️ 本作业既无文字说明、也没有可解析的任务附件，"
                "无法核对「是否达成任务要求」；请只评价提交内容本身，不要臆测任务要求。）"
            )
    else:
        parts.append("（作业信息缺失）")

    parts.append("\n【学生提交内容】")
    body = content_text.strip() if content_text and content_text.strip() else ""
    parts.append(body or "（未填写文字内容）")
    if attachment_text:
        parts.append("\n【附件内容】")
        parts.append(attachment_text)

    if images:
        parts.append(
            f"\n（本条消息另附 {len(images)} 张图片，请结合图片内容评价；"
            "正文中的【图片N】标记与附图顺序一一对应。）"
        )
    else:
        parts.append("\n（本条消息没有可用的图片，请仅依据上述文字评价，不要臆测图片内容。）")

    parts.append("\n请按系统提示的 JSON 格式批改这份作业。")

    text = "\n".join(parts)
    if len(text) > settings.AI_MAX_INPUT_CHARS:
        text = text[: settings.AI_MAX_INPUT_CHARS] + "\n（内容过长已截断）"

    if images:
        content: list[dict] = [{"type": "text", "text": text}]
        for url in images:
            block: dict = {"type": "image_url", "image_url": {"url": url}}
            # 透传 image_url.detail：original 保留原图，low 缩到 512×512 省 token；
            # AI_IMAGE_DETAIL 为空时不带该字段（兼容不走 detail 的模型）。
            if settings.AI_IMAGE_DETAIL:
                block["image_url"]["detail"] = settings.AI_IMAGE_DETAIL
            content.append(block)
        return [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]


# ---------------- 优秀作品自动入库（F4） ----------------
def _maybe_auto_publish(db: Session, result: AiGradingResult, submission: Submission) -> None:
    """自动入库（可配置，默认关闭）：AI 推荐 + 开关开启 → 直接写入 `excellent_works`。

    `selected_by`（NOT NULL）记**开启该配置的超管** —— 配置本身即其授权凭据。
    任何一步不满足都直接返回（退回候选制），**绝不因自动入库失败影响批改结果**。
    """
    if result.status != "success" or not result.is_excellent_candidate:
        return
    if not is_ai_auto_publish_enabled(db):
        return

    existing = (
        db.query(ExcellentWork)
        .filter(ExcellentWork.submission_id == submission.id)
        .first()
    )
    if existing:
        return

    owner_id = get_ai_auto_publish_owner(db)
    if not owner_id:
        logger.warning("已开启自动入库但未记录开启者，退回候选制 submission=%s", submission.id)
        return
    # 开启者是平台超管（school_id 为 NULL），在租户上下文里必须跳过过滤才查得到
    owner = (
        db.query(User)
        .execution_options(skip_tenant_filter=True)
        .filter(User.id == owner_id)
        .first()
    )
    if owner is None:
        logger.warning("自动入库开启者不存在（id=%s），退回候选制", owner_id)
        return

    db.add(
        ExcellentWork(
            submission_id=submission.id,
            selected_by=owner.id,
            # 归属显式取提交所属学校：后台线程虽已 tenant_scope，但若作业的 school_id 为空，
            # ORM 自动填充同样会落成 NULL，该行随后对所有学校不可见。
            school_id=submission.school_id,
            note=(f"AI 推荐自动入库：{result.excellent_reason}".strip("：") if result.excellent_reason else "AI 推荐自动入库"),
            source="ai_recommended",
        )
    )
    audit(
        db,
        owner,
        "ai_auto_publish_excellent",
        target=f"优秀-提交#{submission.id}",
        detail="AI 推荐自动入库",
    )
    db.commit()


# ---------------- 主流程 ----------------
def _content_fingerprint(submission: Submission) -> str:
    """提交「批改依据」的内容指纹（正文 + 附件路径）。"""
    payload = f"{submission.content or ''}\x00{submission.filepath or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _submission_changed(db: Session, submission: Submission, fingerprint: str) -> bool:
    """模型调用期间该提交是否被重交（内容指纹变化）；行已被删除也视为已变。"""
    try:
        db.refresh(submission)
    except Exception:  # 行被删除 → 结果无处安放，按「已变化」处理
        return True
    return _content_fingerprint(submission) != fingerprint


_TRUNCATION_RETRY_FACTOR = 3


def _call_model(cred, messages: list[dict], max_tokens: int) -> dict:
    """调用模型；输出被截断（含正文被思考挤空）时用更大预算重试**一次**。

    推理模型下，思考 token 与正文共用 max_tokens 预算，极端情况下正文仍可能被挤空
    （finish_reason == "length" 但 content 为空，或 content 非空但被截断）。此时用更大
    预算重试一次，可能拿到完整正文；超过上限（AI_MAX_TOKENS_CEILING）则不再放大。
    """
    def invoke(budget: int) -> dict:
        return chat_completion(
            base_url=cred.base_url,
            api_key=decrypt_secret(cred.api_key_encrypted),
            model=cred.model,
            messages=messages,
            max_tokens=budget,
            thinking=settings.AI_THINKING_MODE or None,
            reasoning_effort=settings.AI_REASONING_EFFORT or None,
        )

    bigger = min(max_tokens * _TRUNCATION_RETRY_FACTOR, settings.AI_MAX_TOKENS_CEILING)

    try:
        response = invoke(max_tokens)
    except AiClientError as exc:
        # 正文被思考挤空（finish_reason == length 但 content 为空）属可重试的截断
        if getattr(exc, "truncated", False) and bigger > max_tokens:
            logger.warning(
                "AI 批改输出被截断（正文为空），加大预算重试 max_tokens=%s→%s",
                max_tokens,
                bigger,
            )
            return invoke(bigger)
        raise

    # 正文非空但仍被 length 截断（JSON 可能不完整）→ 用更大预算重试一次，
    # 仅当重试拿到非空正文才采纳，否则保留原结果交给诚实性守卫判 failed。
    if response.get("finish_reason") == "length" and bigger > max_tokens:
        logger.warning(
            "AI 批改输出被截断，加大预算重试 max_tokens=%s→%s", max_tokens, bigger
        )
        retry = invoke(bigger)
        if (retry.get("content") or "").strip():
            return retry
    return response


def grade_submission(db: Session, submission_id: int) -> AiGradingResult:
    """执行一次批改并落库。

    调用方必须已处于**正确的租户上下文**（见 `_run_grading`）。
    业务失败（模型报错等）记 `failed` 后正常返回，不抛异常；
    只有编程错误才会向上抛，由 `_run_grading` 兜底。
    """
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise AiClientError("提交不存在")
    # 提交归属学校：用于显式回填结果行的 school_id（见下方 pending 落库与诚实性守卫）。
    # 后台线程租户上下文可能为 None（作业 school_id 为 NULL），此时 ORM `before_flush`
    # 自动填充是空操作，结果行会落成对所有租户不可见，故必须显式携带。
    owner_school_id = submission.school_id
    # 记录批改所依据的**内容版本**：模型调用是慢 I/O，期间学生可能重交
    # （`submit` 会原地改写 content 并作废旧结果）。成功写回前必须确认内容未变，
    # 否则结果会被贴到一份它从未批过的新内容上（见 `_submission_changed`）。
    content_fingerprint = _content_fingerprint(submission)

    cred = active_credential(db)
    if cred is None:
        return _upsert_result(
            db,
            submission_id,
            status="failed",
            error="AI 凭证未配置、未启用或密钥不可用",
        )

    assignment = db.get(Assignment, submission.assignment_id)
    # ① 任务附件：先抽，让它优先占用图片名额 —— 它定义「要做什么」，缺了就无法判断完成度。
    requirement_text, requirement_images, requirement_notes = (
        _extract_assignment_materials(
            assignment,
            vision_enabled=cred.vision_enabled,
            max_images=max(
                0, settings.AI_MAX_IMAGES - _RESERVED_IMAGE_SLOTS_FOR_SUBMISSION
            ),
        )
    )
    # ② 学生提交附件。filepath 只承载「单个上传附件」；学生用富文本编辑器插入的图片写在
    # content 里的 Markdown（`![](/uploads/x.png)`），filepath 仍为空 —— 必须单独抽取，
    # 否则模型只拿到一串访问不到的 URL，完全看不到图片（历史缺陷）。
    payload = extract_attachment(
        submission.filepath, submission.filename, vision_enabled=cred.vision_enabled
    )
    # ③ 内嵌图片按「剩余预算」抽取：全局合计不超过 AI_MAX_IMAGES（修缺陷 5）。
    # 例如任务附件 + 提交附件已占 2 张，正文内嵌最多再取 AI_MAX_IMAGES - 2 张。
    inline = extract_inline_images(
        submission.content or "",
        vision_enabled=cred.vision_enabled,
        max_images=max(
            0, settings.AI_MAX_IMAGES - len(requirement_images) - len(payload.images)
        ),
    )
    images = requirement_images + payload.images + inline.images

    # 整批图片总字节护栏：data URL 累加超过 AI_IMAGE_MAX_TOTAL_BYTES 的丢弃
    # （保持顺序、靠前优先），并追加说明。说明并入现有 attachment_used 的组装方式，
    # 不新增数据库字段。
    kept_images: list[str] = []
    total = 0
    dropped = 0
    for url in images:
        total += len(url)
        if total > settings.AI_IMAGE_MAX_TOTAL_BYTES:
            dropped += 1
            continue
        kept_images.append(url)
    images = kept_images

    note_parts = [*requirement_notes, payload.note, *inline.notes]
    if dropped:
        note_parts.append(
            f"图片过多（{dropped} 张因总体积超过 "
            f"{settings.AI_IMAGE_MAX_TOTAL_BYTES // (1024 * 1024)}MB 上限未参与批改）"
        )
    note = "；".join(n for n in note_parts if n)
    messages = _build_messages(
        assignment, inline.text, payload.text, images, requirement_text
    )

    # 先落 pending：前端可立即显示「批改中」
    result = _upsert_result(
        db,
        submission_id,
        status="pending",
        provider=cred.provider,
        model=cred.model,
        attachment_used=note,
        error=None,
        school_id=owner_school_id,
    )
    db.commit()

    try:
        response = _call_model(cred, messages, get_ai_max_tokens(db))
    except AiClientError as exc:
        # 降级：提交早已成功，这里只把失败原因记给教师看
        result.status = "failed"
        result.error = str(exc)
        if images:
            # 带图调用失败时，最常见的原因是所配模型不支持图片输入。给出可操作提示，
            # 否则「图片明明传了、批改却失败」在生产里很难排查。
            result.error += (
                f"（本次批改包含 {len(images)} 张图片；若上游模型不支持图片输入，"
                "请在平台设置中关闭「多模态」或改配支持视觉的模型）"
            )
        db.commit()
        logger.warning("AI 批改失败 submission=%s：%s", submission_id, exc)
        return result

    parsed = parse_model_output(response["content"])
    usage = response.get("usage") or {}
    # 🔴 重交竞态兜底：批改期间若提交内容已变化，本次结果对当前提交**无效** ——
    # 记 failed 让教师看到「需重新批改」，而不是把结果贴到它从未批过的新内容上。
    if _submission_changed(db, submission, content_fingerprint):
        logger.info("提交内容在批改期间已更新，丢弃本次结果 submission=%s", submission_id)
        result = _upsert_result(
            db,
            submission_id,
            status="failed",
            error="提交内容在批改期间已更新，本次结果已作废，请重新批改",
        )
        db.commit()
        return result

    # 诚实性守卫：模型输出被截断（非合法 JSON）或未解析成功时，绝不假装成功 ——
    # 否则教师会看到「有总评、没亮点/改进建议」的残缺批改。桩/旧调用不带
    # finish_reason（为 None）→ 视为未截断，保持向后兼容。
    truncated = response.get("finish_reason") == "length"
    if truncated or not parsed.get("parsed", False):
        result = _upsert_result(
            db,
            submission_id,
            status="failed",
            raw_response=response["content"],
            error=(
                "模型输出被截断（超出单次调用上限），未生成完整批改，请调高平台设置中的"
                "「单次调用 max_tokens」后重新批改（可尝试关闭模型思考模式或调高单次调用 max_tokens）"
                if truncated
                else "模型返回内容不是预期的 JSON 结构，未生成完整批改，请重新批改或更换模型"
            ),
            school_id=owner_school_id,
        )
        db.commit()
        logger.warning(
            "AI 批改结果不完整，标记 failed submission=%s truncated=%s reasoning_tokens=%s",
            submission_id,
            truncated,
            response.get("reasoning_tokens"),
        )
        return result

    result.status = "success"
    result.error = None
    result.summary = parsed["summary"] or None
    result.strengths = parsed["strengths"] or None
    result.improvements = parsed["improvements"] or None
    result.score = parsed["score"]
    result.is_excellent_candidate = parsed["is_excellent_candidate"]
    result.excellent_reason = parsed["excellent_reason"] or None
    result.raw_response = response["content"]
    result.prompt_tokens = usage.get("prompt_tokens")
    result.completion_tokens = usage.get("completion_tokens")
    db.commit()

    _maybe_auto_publish(db, result, submission)
    return result


def _run_grading(submission_id: int, school_id: int | None) -> None:
    """线程池任务入口：自建 session + 显式租户上下文 + 全异常兜底。"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        with tenant_scope(school_id):
            grade_submission(db, submission_id)
    except Exception:
        logger.exception(
            "AI 批改任务异常（已降级，不影响学生提交） submission=%s", submission_id
        )
        try:
            db.rollback()
            with tenant_scope(school_id):
                # 显式带归属：租户上下文为 None 时 ORM 自动填充是空操作，
                # 失败行会落成 school_id=NULL 而对所有租户不可见。
                _upsert_result(
                    db,
                    submission_id,
                    school_id=school_id,
                    status="failed",
                    error="批改任务内部错误",
                )
                db.commit()
        except Exception:
            logger.exception("记录批改失败状态时再次异常 submission=%s", submission_id)
    finally:
        db.close()


def trigger_grading(submission_id: int, school_id: int | None) -> None:
    """把批改任务提交到线程池（非阻塞）。"""
    _executor.submit(_run_grading, submission_id, school_id)


def _apply_prewrite(
    db: Session, submission_ids: list[int], school_id: int | None, cred
) -> None:
    """把一批提交预写成 `pending` 结果行（**显式**写归属 + 跳过租户过滤）。

    拆成独立函数是为了能在 commit 撞唯一索引后整体重放一次（见 `_prewrite_pending`）。
    """
    existing = {
        r.submission_id: r
        for r in db.query(AiGradingResult)
        # 全局唯一键，行的身份与租户无关；带过滤会读不到归属异常的行 → 重复 INSERT。
        .execution_options(skip_tenant_filter=True)
        .filter(AiGradingResult.submission_id.in_(submission_ids))
        .all()
    }
    for sid in submission_ids:
        row = existing.get(sid)
        if row is None:
            row = AiGradingResult(submission_id=sid)
            db.add(row)
        # 显式归属：触发方可能是平台超管（JWT 无 school_id）→ 租户上下文为 None，
        # 此时 ORM `before_flush` 自动填充是空操作，行会落成 school_id=NULL、
        # 对所有租户不可见，随后被租户过滤挡住 → 重复 INSERT → 1062
        # （2026-09-22 线上事故）。仅在为空时回填，绝不覆盖已有归属。
        if school_id is not None and row.school_id is None:
            row.school_id = school_id
        row.status = "pending"
        row.provider = cred.provider if cred else None
        row.model = cred.model if cred else None
        row.error = None


def _prewrite_pending(
    db: Session, submission_ids: list[int], school_id: int | None
) -> None:
    """投递前预写 pending；并发双击撞唯一键时回滚后重放一次（转为 UPDATE）。"""
    if not submission_ids:
        return
    cred = active_credential(db)
    try:
        _apply_prewrite(db, submission_ids, school_id, cred)
        db.commit()
    except IntegrityError:
        db.rollback()
        _apply_prewrite(db, submission_ids, school_id, cred)
        db.commit()


def request_grading(
    db: Session, submission_ids: list[int], school_id: int | None
) -> dict:
    """教师手动触发的统一入口：校验总开关/凭证/额度后投递线程池。

    额度是**平台级唯一成本刹车**，因此批量触发必须先**原子预留**额度再投递，
    按预留到的数量截断 —— 宁可少批几份并如实回报，也不能投出超过额度的任务
    （`reserve_quota` 把「检查 + 占用」合并，避免并发下各自满额投递而超发）。

    Returns:
        ``{queued, skipped, reason}``：实际投递数、因额度不足被截断的份数、
        以及完全无法批改时的原因（可批改时为空串）。
    """
    allowed, reason = can_grade(db)
    if not allowed:
        return {"queued": 0, "skipped": len(submission_ids), "reason": reason}

    # 🔴 先**原子预留**额度，再按预留到的数量投递：把「查额度 → 截断 → 投递」三步
    # 合成一个原子操作，消除并发批量触发各自按同一份剩余额度满额投递导致的超发
    # （额度是平台级唯一成本刹车，超发即护栏失效）。
    take = reserve_quota(db, len(submission_ids))
    queued = submission_ids[:take]

    # 投递前预写 pending：进程重启/重载时，尚未开跑的排队任务若一行痕迹都没有，
    # 会静默消失且无可兜底；这里先落 pending + provider/model，便于恢复与对账。
    _prewrite_pending(db, queued, school_id)

    for submission_id in queued:
        trigger_grading(submission_id, school_id)
    logger.info(
        "AI 批改已投递 %s 份（跳过 %s 份）", len(queued), len(submission_ids) - len(queued)
    )
    return {"queued": len(queued), "skipped": len(submission_ids) - len(queued), "reason": ""}


# ---------------- 启动兜底：清理中断的 pending ----------------
def _parse_db_datetime(value) -> datetime | None:
    """把数据库时钟归一化成 `datetime`。

    不同驱动的 `func.now()` 返回类型不一致：MySQL 返回 `datetime`，SQLite 返回
    字符串（如 ``"2026-09-22 21:00:00"``，可能带小数秒）。统一成 `datetime`
    便于与结果行的时间戳比较，避免把 Python 本地时间与数据库服务端时间混用。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)  # noqa: DTZ001
    s = str(value).strip().replace("T", " ")
    if "." in s:
        s = s.split(".", 1)[0]
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
    except ValueError:
        return None


def reconcile_stale_pending(db: Session, older_than_seconds: int = 600) -> int:
    """把上次进程中断遗留的 `pending` 批改标记为失败，避免教师永远看到「批改中」。

    必须与调用方租户上下文无关：`status == "pending"` 的查询用
    `skip_tenant_filter=True`，否则租户上下文为空时查不到任何行、兜底失效。

    两侧时间**都用数据库时钟**（`func.now()` 与行时间戳同库同源），不掺入 Python
    本地时间。任何内部异常都吞掉并返回 0，绝不能影响应用启动。

    Returns:
        被标记为失败的行数。
    """
    try:
        raw_now = db.execute(select(func.now())).scalar()
        db_now = _parse_db_datetime(raw_now)
        if db_now is None:
            return 0
        cutoff = db_now - timedelta(seconds=older_than_seconds)

        rows = (
            db.query(AiGradingResult)
            .execution_options(skip_tenant_filter=True)
            .filter(AiGradingResult.status == "pending")
            .all()
        )
        count = 0
        for row in rows:
            ts = _parse_db_datetime(row.updated_at) or _parse_db_datetime(row.created_at)
            if ts is not None and ts < cutoff:
                row.status = "failed"
                row.error = "批改中断（服务重启），请重新发起批改"
                count += 1
        if count:
            db.commit()
        return count
    except Exception:
        logger.exception("清理中断的 AI 批改 pending 行失败（忽略）")
        return 0
