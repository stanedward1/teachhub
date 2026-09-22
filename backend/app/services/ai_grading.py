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
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import settings
from app.crypto import decrypt_secret
from app.models import (
    AiCredential,
    AiGradingResult,
    Assignment,
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
from app.services.ai_attachments import extract_attachment
from app.services.ai_client import AiClientError, chat_completion
from app.tenant import tenant_scope

logger = logging.getLogger("teachhub.ai")

# 后台批改线程数：批改是 I/O 密集（等模型返回），2 个并发足以消化一个班的提交量，
# 又不会把上游服务打爆或抢占太多连接。
_MAX_WORKERS = 2
_executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="ai-grading")

_SYSTEM_PROMPT = """你是一位经验丰富的大专院校及职业高中的专业教师，正在批改学生的上机作业。
请客观、具体、以鼓励为主地评价，指出亮点并给出可执行的改进建议。

评价依据】
只依据本条消息中的【作业要求】、【学生提交内容】、【附件内容】，以及随消息附上的图片
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
  "strengths": "优点，分条书写，每条以 - 开头",
  "improvements": "改进建议，分条书写，每条以 - 开头",
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


def today_call_count(db: Session) -> int:
    """当日已发生的批改调用次数（平台级口径，跨租户统计）。

    总开关是平台级的（§8 Q1 无按校粒度），因此成本护栏也必须按平台统计 ——
    这里显式 `skip_tenant_filter`，否则会被 ORM 过滤成「本校次数」而低估成本。

    ⚠️ 「今天」的边界**必须交给数据库计算**，不能用 Python 的 `date.today()`：
    `created_at` 是数据库 `server_default=func.now()` 生成的（SQLite 为 **UTC**，
    MySQL 为**库本地时区**），而 Python 的 `date.today()` 取的是**进程本地日期**。
    两者时区不一致时（例如 SQLite 下 03:20 CST 属于 UTC 前一天），
    `created_at >= 本地今日零点` 会把当天的记录全部过滤掉，
    使计数恒为 0、**限额永不触发**（成本护栏静默失效）。
    用 `func.date(created_at) == func.current_date()` 保证两侧同一时间基准。
    """
    return (
        db.query(func.count(AiGradingResult.id))
        .execution_options(skip_tenant_filter=True)
        .filter(
            func.date(AiGradingResult.created_at) == func.current_date(),
            AiGradingResult.status.in_(("success", "failed")),
        )
        .scalar()
        or 0
    )


def remaining_quota(db: Session) -> int:
    """今日剩余可批改次数（平台级口径，跨租户统计；额度耗尽返回 0）。"""
    return max(get_ai_daily_limit(db) - today_call_count(db), 0)


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
def _upsert_result(db: Session, submission_id: int, **fields) -> AiGradingResult:
    """按 `submission_id` 更新或新建结果行（重跑覆盖，天然幂等）。"""
    result = (
        db.query(AiGradingResult)
        .filter(AiGradingResult.submission_id == submission_id)
        .first()
    )
    if result is None:
        result = AiGradingResult(submission_id=submission_id)
        db.add(result)
    for key, value in fields.items():
        setattr(result, key, value)
    return result


def _build_messages(
    assignment: Assignment | None,
    submission: Submission,
    attachment_text: str,
    attachment_images: list[str],
) -> list[dict]:
    """构造批改请求消息（作业要求 + 学生正文 + 附件内容）。"""
    parts: list[str] = ["【作业要求】"]
    if assignment is not None:
        parts.append(f"标题：{assignment.title}")
        if assignment.description:
            parts.append(f"说明：{assignment.description}")
        if assignment.content:
            parts.append(f"正文：\n{assignment.content}")
    else:
        parts.append("（作业信息缺失）")

    parts.append("\n【学生提交内容】")
    parts.append(submission.content.strip() if submission.content else "（未填写文字内容）")
    if attachment_text:
        parts.append("\n【附件内容】")
        parts.append(attachment_text)
    parts.append("\n请按系统提示的 JSON 格式批改这份作业。")

    text = "\n".join(parts)
    if len(text) > settings.AI_MAX_INPUT_CHARS:
        text = text[: settings.AI_MAX_INPUT_CHARS] + "\n（内容过长已截断）"

    if attachment_images:
        content: list[dict] = [{"type": "text", "text": text}]
        content.extend(
            {"type": "image_url", "image_url": {"url": url}} for url in attachment_images
        )
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
def grade_submission(db: Session, submission_id: int) -> AiGradingResult:
    """执行一次批改并落库。

    调用方必须已处于**正确的租户上下文**（见 `_run_grading`）。
    业务失败（模型报错等）记 `failed` 后正常返回，不抛异常；
    只有编程错误才会向上抛，由 `_run_grading` 兜底。
    """
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise AiClientError("提交不存在")

    cred = active_credential(db)
    if cred is None:
        return _upsert_result(
            db,
            submission_id,
            status="failed",
            error="AI 凭证未配置、未启用或密钥不可用",
        )

    assignment = db.get(Assignment, submission.assignment_id)
    payload = extract_attachment(
        submission.filepath, submission.filename, vision_enabled=cred.vision_enabled
    )
    messages = _build_messages(assignment, submission, payload.text, payload.images)

    # 先落 pending：前端可立即显示「批改中」
    result = _upsert_result(
        db,
        submission_id,
        status="pending",
        provider=cred.provider,
        model=cred.model,
        attachment_used=payload.note,
        error=None,
    )
    db.commit()

    try:
        response = chat_completion(
            base_url=cred.base_url,
            api_key=decrypt_secret(cred.api_key_encrypted),
            model=cred.model,
            messages=messages,
            max_tokens=get_ai_max_tokens(db),
        )
    except AiClientError as exc:
        # 降级：提交早已成功，这里只把失败原因记给教师看
        result.status = "failed"
        result.error = str(exc)
        db.commit()
        logger.warning("AI 批改失败 submission=%s：%s", submission_id, exc)
        return result

    parsed = parse_model_output(response["content"])
    usage = response.get("usage") or {}
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
                _upsert_result(db, submission_id, status="failed", error="批改任务内部错误")
                db.commit()
        except Exception:
            logger.exception("记录批改失败状态时再次异常 submission=%s", submission_id)
    finally:
        db.close()


def trigger_grading(submission_id: int, school_id: int | None) -> None:
    """把批改任务提交到线程池（非阻塞）。"""
    _executor.submit(_run_grading, submission_id, school_id)


def request_grading(
    db: Session, submission_ids: list[int], school_id: int | None
) -> dict:
    """教师手动触发的统一入口：校验总开关/凭证/额度后投递线程池。

    额度是**平台级唯一成本刹车**，因此批量触发时必须按剩余额度截断 ——
    宁可少批几份并如实回报，也不能一次性投出超过额度的任务（那样会绕过护栏）。

    Returns:
        ``{queued, skipped, reason}``：实际投递数、因额度不足被截断的份数、
        以及完全无法批改时的原因（可批改时为空串）。
    """
    allowed, reason = can_grade(db)
    if not allowed:
        return {"queued": 0, "skipped": len(submission_ids), "reason": reason}

    queued = submission_ids[: remaining_quota(db)]
    for submission_id in queued:
        trigger_grading(submission_id, school_id)
    logger.info(
        "AI 批改已投递 %s 份（跳过 %s 份）", len(queued), len(submission_ids) - len(queued)
    )
    return {"queued": len(queued), "skipped": len(submission_ids) - len(queued), "reason": ""}
